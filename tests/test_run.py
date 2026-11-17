import json
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest

from pipeline import db, ingest, report
from pipeline.report import IncidentReport
from pipeline.run import run_pipeline, run_with_db

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
DB_URL = "postgresql://cctv:cctv@localhost:5433/cctv"


@pytest.fixture
def fake_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the LLM call so tests never hit the API."""

    def fake(candidates, meta, sampling, **_):
        return IncidentReport(summary="fake", incidents=[]), "fake-model"

    monkeypatch.setattr(report, "generate_report", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.mark.parametrize(("sampling", "n_frames"), [("scene", 3), ("interval", 6), ("hybrid", 6)])
def test_pipeline_writes_events_json(synthetic_clip: Path, tmp_path: Path, sampling: str, n_frames: int) -> None:
    result = run_pipeline(synthetic_clip, out_root=tmp_path, sampling=sampling, job_id="job1", with_report=False)
    job_dir = tmp_path / "job1"

    assert (job_dir / "normalised.mp4").exists()
    assert json.loads((job_dir / "events.json").read_text()) == result
    assert set(result["timings_s"]) == {"ingest", "keyframes", "detect"}
    assert result["sampling"]["mode"] == sampling
    assert len(result["keyframes"]) == n_frames
    assert all(Path(k["path"]).exists() for k in result["keyframes"])
    assert result["report"] is None


def test_pipeline_reports_status_and_report(synthetic_clip: Path, tmp_path: Path, fake_report: None) -> None:
    seen: list[str] = []
    result = run_pipeline(synthetic_clip, out_root=tmp_path, on_status=seen.append)
    assert seen == ["ingesting", "keyframes", "detecting", "reporting"]
    assert result["report"] == {"model": "fake-model", "summary": "fake", "incidents": []}
    assert "report" in result["timings_s"]


def test_run_with_db_persists_job(synthetic_clip: Path, tmp_path: Path, fake_report: None) -> None:
    try:
        conn = db.connect(DB_URL)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    try:
        run_with_db(conn, job_id, synthetic_clip, out_root=tmp_path)
        job = db.get_job(conn, job_id)
        assert job["status"] == "done" and job["meta"]["fps"] == 25.0
        assert db.get_report(conn, job_id)["summary"] == "fake"
    finally:
        conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.commit()
        conn.close()


def test_run_with_db_marks_failed(tmp_path: Path) -> None:
    try:
        conn = db.connect(DB_URL)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable")
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    try:
        with pytest.raises(ingest.IngestError):
            run_with_db(conn, job_id, tmp_path / "missing.mp4", out_root=tmp_path, with_report=False)
        job = db.get_job(conn, job_id)
        assert job["status"] == "failed" and "not found" in job["error"]
    finally:
        conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.commit()
        conn.close()


def test_missing_key_fails_before_video_work(
    synthetic_clip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(report.ReportError, match="ANTHROPIC_API_KEY"):
        run_pipeline(synthetic_clip, out_root=tmp_path, job_id="nokey")
    assert not (tmp_path / "nokey").exists()  # nothing was transcoded
