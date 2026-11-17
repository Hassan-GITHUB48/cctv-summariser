"""Postgres persistence for jobs, detection events and reports (psycopg 3)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
JOB_STATUSES = ("queued", "ingesting", "keyframes", "detecting", "reporting", "done", "failed")
_UPDATABLE = {"status", "error", "failed_stage", "meta", "sampling", "timings"}
_JSON_COLUMNS = {"meta", "sampling", "timings"}


def connect(url: str | None = None) -> psycopg.Connection[dict[str, Any]]:
    """Open a connection to ``url`` (default: ``$DATABASE_URL``) that returns rows as dicts."""
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    return psycopg.connect(url, row_factory=dict_row)


def init_schema(conn: psycopg.Connection) -> None:
    """Create tables if they don't exist (the schema file is idempotent)."""
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()


def create_job(conn: psycopg.Connection, job_id: str, source: str) -> None:
    """Insert a new job in the ``queued`` state."""
    conn.execute("INSERT INTO jobs (id, source) VALUES (%s, %s)", (job_id, source))
    conn.commit()


def update_job(conn: psycopg.Connection, job_id: str, **fields: Any) -> None:
    """Update whitelisted job columns, e.g. ``update_job(conn, id, status="detecting")``."""
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"Cannot update job columns: {sorted(unknown)}")
    if fields.get("status") not in (None, *JOB_STATUSES):
        raise ValueError(f"Invalid status: {fields['status']}")
    assignments = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(col)) for col in fields)
    values = [Jsonb(v) if col in _JSON_COLUMNS else v for col, v in fields.items()]
    conn.execute(
        sql.SQL("UPDATE jobs SET {}, updated_at = now() WHERE id = %s").format(assignments),
        [*values, job_id],
    )
    conn.commit()


def fail_interrupted_jobs(conn: psycopg.Connection) -> int:
    """Mark jobs left mid-pipeline (e.g. by a server restart) as failed; returns how many."""
    cur = conn.execute(
        "UPDATE jobs SET status = 'failed', error = 'Interrupted by server restart', updated_at = now()"
        " WHERE status NOT IN ('done', 'failed')"
    )
    conn.commit()
    return cur.rowcount


def insert_events(conn: psycopg.Connection, job_id: str, events: list[dict]) -> int:
    """Replace all events for ``job_id`` with ``events`` (dicts from ``Event.to_dict``)."""
    with conn.transaction():
        conn.execute("DELETE FROM events WHERE job_id = %s", (job_id,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO events (job_id, timestamp_s, frame_index, label, confidence, bbox, frame_path)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        job_id,
                        e["timestamp_s"],
                        e["frame_index"],
                        e["label"],
                        e["confidence"],
                        list(e["bbox"]),
                        e["frame_path"],
                    )
                    for e in events
                ],
            )
    return len(events)


def save_report(conn: psycopg.Connection, job_id: str, model: str, summary: str, incidents: list[dict]) -> None:
    """Insert or replace the report for ``job_id``."""
    conn.execute(
        "INSERT INTO reports (job_id, model, summary, incidents) VALUES (%s, %s, %s, %s)"
        " ON CONFLICT (job_id) DO UPDATE SET model = EXCLUDED.model, summary = EXCLUDED.summary,"
        " incidents = EXCLUDED.incidents, created_at = now()",
        (job_id, model, summary, Jsonb(incidents)),
    )
    conn.commit()


def get_job(conn: psycopg.Connection, job_id: str) -> dict | None:
    """Return the job row or ``None``."""
    return conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()


def get_events(conn: psycopg.Connection, job_id: str) -> list[dict]:
    """Return a job's events ordered by time."""
    return conn.execute(
        "SELECT timestamp_s, frame_index, label, confidence, bbox, frame_path"
        " FROM events WHERE job_id = %s ORDER BY timestamp_s, confidence DESC",
        (job_id,),
    ).fetchall()


def get_report(conn: psycopg.Connection, job_id: str) -> dict | None:
    """Return the report row or ``None``."""
    return conn.execute("SELECT * FROM reports WHERE job_id = %s", (job_id,)).fetchone()
