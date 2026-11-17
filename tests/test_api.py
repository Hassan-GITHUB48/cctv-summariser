"""API tests: real Postgres (skipped if unreachable), real pipeline, fake LLM."""

import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
import ultralytics
from fastapi.testclient import TestClient

from api.config import Settings
from api.jobs import stage_progress
from api.main import create_app
from pipeline import db, report
from pipeline.report import IncidentReport

DB_URL = "postgresql://cctv:cctv@localhost:5433/cctv"
BUS = Path(ultralytics.__file__).parent / "assets" / "bus.jpg"


def _db_available() -> bool:
    try:
        psycopg.connect(DB_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


needs_stack = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not _db_available(), reason="needs ffmpeg and docker compose Postgres"
)


@pytest.fixture(scope="module")
def bus_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """4 s video of the bundled bus.jpg (people + a bus), so YOLO has something to find."""
    out = tmp_path_factory.mktemp("clips") / "bus.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(BUS), "-t", "4", "-r", "25",
                    "-vf", "scale=-2:720", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(report, "generate_report",
                        lambda cands, *a, **k: (IncidentReport(summary=f"{len(cands)} candidates", incidents=[]), "fake"))
    settings = Settings(database_url=DB_URL, output_dir=tmp_path / "out", upload_dir=tmp_path / "up", max_upload_mb=50)
    with TestClient(create_app(settings)) as c:  # `with` runs the lifespan (pool, schema)
        yield c


def upload(client: TestClient, path: Path, name: str | None = None) -> "object":
    with path.open("rb") as f:
        return client.post("/jobs", files={"video": (name or path.name, f, "video/mp4")},
                           data={"start_time": "2026-11-16T23:30:00"})


@needs_stack
def test_full_job_flow(client: TestClient, bus_clip: Path) -> None:
    resp = upload(client, bus_clip)
    assert resp.status_code == 202 and resp.json()["status"] == "queued"
    job_id = resp.json()["job_id"]

    # TestClient runs background tasks before returning, so the job has finished.
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "done" and job["progress"] == 1.0, job
    assert [s["state"] for s in job["stages"]] == ["done"] * 4
    assert job["meta"]["height"] == 720 and set(job["timings"]) >= {"ingest", "detect", "report"}

    events = client.get(f"/jobs/{job_id}/events").json()
    assert events and {e["label"] for e in events} >= {"person"}
    frame = client.get(events[0]["frame_url"])
    assert frame.status_code == 200 and frame.headers["content-type"] == "image/jpeg"

    rep = client.get(f"/jobs/{job_id}/report").json()
    assert rep["model"] == "fake" and rep["summary"].endswith("candidates")

    video = client.get(f"/jobs/{job_id}/video", headers={"Range": "bytes=0-99"})
    assert video.status_code == 206 and len(video.content) == 100  # range requests let the player seek


@needs_stack
def test_upload_validation(client: TestClient, tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("hello")
    assert upload(client, text).status_code == 415
    fake_mp4 = tmp_path / "fake.mp4"
    fake_mp4.write_text("not a video")
    assert upload(client, fake_mp4).status_code == 422


@needs_stack
def test_upload_too_large(tmp_path: Path, bus_clip: Path) -> None:
    settings = Settings(database_url=DB_URL, output_dir=tmp_path / "o", upload_dir=tmp_path / "u", max_upload_mb=0)
    with TestClient(create_app(settings)) as c:
        assert upload(c, bus_clip).status_code == 413


@needs_stack
def test_not_found_and_bad_ids(client: TestClient) -> None:
    assert client.get("/jobs/doesnotexist").status_code == 404
    assert client.get("/jobs/BAD!ID").status_code == 422
    assert client.get("/jobs/doesnotexist/events").status_code == 404


@needs_stack
def test_frames_cannot_escape_output_dir(client: TestClient) -> None:
    assert client.get("/frames/%2e%2e/%2e%2e/pyproject.toml").status_code == 404
    assert client.get("/frames/%2e%2e%2f%2e%2e%2fsecret.jpg").status_code == 404


@needs_stack
def test_report_409_while_running(client: TestClient) -> None:
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DB_URL) as conn:
        db.create_job(conn, job_id, "x.mp4")
        db.update_job(conn, job_id, status="detecting")
    try:
        assert client.get(f"/jobs/{job_id}/report").status_code == 409
        job = client.get(f"/jobs/{job_id}").json()
        assert job["progress"] == 0.5
        assert [s["state"] for s in job["stages"]] == ["done", "done", "running", "pending"]
    finally:
        with psycopg.connect(DB_URL) as conn:
            conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))


@pytest.mark.parametrize(("status", "failed_stage", "states", "progress"), [
    ("queued", None, ["pending"] * 4, 0.0),
    ("ingesting", None, ["running", "pending", "pending", "pending"], 0.0),
    ("reporting", None, ["done", "done", "done", "running"], 0.75),
    ("done", None, ["done"] * 4, 1.0),
    ("failed", "detecting", ["done", "done", "failed", "pending"], 0.5),
    ("failed", None, ["failed", "pending", "pending", "pending"], 0.0),
])
def test_stage_progress(status: str, failed_stage: str | None, states: list[str], progress: float) -> None:
    got_progress, stages = stage_progress(status, failed_stage)
    assert [s.state for s in stages] == states and got_progress == progress


def test_runner_limits_concurrency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With max_concurrent=1, jobs run one at a time and the others wait (stay queued)."""
    import contextlib
    import threading
    import time

    from api.jobs import JobRunner
    from pipeline import run

    active, peak, lock = 0, 0, threading.Lock()

    def fake_run(conn, job_id, video, **_):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1

    monkeypatch.setattr(run, "run_with_db", fake_run)
    pool = type("FakePool", (), {"connection": lambda self: contextlib.nullcontext()})()
    runner = JobRunner(pool, tmp_path, max_concurrent=1)
    threads = [threading.Thread(target=runner.process, args=(f"j{i}", tmp_path / f"u{i}" / "v.mp4"))
               for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1
