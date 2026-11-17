"""Integration tests against the docker-compose Postgres; skipped if it isn't reachable."""

import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from pipeline import db

DB_URL = os.environ.get("DATABASE_URL", "postgresql://cctv:cctv@localhost:5433/cctv")


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    try:
        connection = db.connect(DB_URL)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (run: docker compose up -d)")
    db.init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def job_id(conn: psycopg.Connection) -> Iterator[str]:
    jid = f"test-{uuid.uuid4().hex[:8]}"
    db.create_job(conn, jid, "samples/clip.mp4")
    yield jid
    conn.execute("DELETE FROM jobs WHERE id = %s", (jid,))  # cascades to events/reports
    conn.commit()


EVENT = {"timestamp_s": 2.0, "frame_index": 24, "label": "person", "confidence": 0.87,
         "bbox": (10, 20, 110, 220), "frame_path": "output/x/frames/frame_000024.jpg"}


def test_job_lifecycle(conn: psycopg.Connection, job_id: str) -> None:
    assert db.get_job(conn, job_id)["status"] == "queued"
    db.update_job(conn, job_id, status="done", timings={"ingest": 0.4})
    job = db.get_job(conn, job_id)
    assert job["status"] == "done" and job["timings"] == {"ingest": 0.4}


def test_update_job_rejects_bad_input(conn: psycopg.Connection, job_id: str) -> None:
    with pytest.raises(ValueError):
        db.update_job(conn, job_id, id="hijack")
    with pytest.raises(ValueError):
        db.update_job(conn, job_id, status="bogus")


def test_insert_events_replaces_previous(conn: psycopg.Connection, job_id: str) -> None:
    db.insert_events(conn, job_id, [EVENT, {**EVENT, "timestamp_s": 4.0}])
    db.insert_events(conn, job_id, [EVENT])  # re-run must not duplicate
    events = db.get_events(conn, job_id)
    assert len(events) == 1
    assert events[0]["bbox"] == [10, 20, 110, 220]


def test_save_report_upserts(conn: psycopg.Connection, job_id: str) -> None:
    db.save_report(conn, job_id, "m1", "first", [])
    db.save_report(conn, job_id, "m2", "second", [{"title": "x"}])
    report = db.get_report(conn, job_id)
    assert (report["model"], report["summary"], report["incidents"]) == ("m2", "second", [{"title": "x"}])
