"""FastAPI app: upload a video, poll job status, fetch events, report, frames and the normalised video.

Run with:  uvicorn api.main:create_app --factory --reload
"""

from __future__ import annotations

import logging
import shutil
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.config import Settings
from api.jobs import ALLOWED_EXTENSIONS, JobRunner, UploadTooLarge, save_upload, stage_progress
from api.schemas import EventOut, JobCreated, JobStatus, ReportOut
from pipeline import db, ingest

log = logging.getLogger(__name__)
JobId = Annotated[str, PathParam(pattern=r"^[a-z0-9-]{1,40}$")]


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """Borrow a pooled connection for the duration of one request."""
    with request.app.state.pool.connection() as conn:
        yield conn


# Module level on purpose: with postponed annotations FastAPI resolves these names from module globals.
Conn = Annotated[psycopg.Connection, Depends(get_conn)]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app (an app factory, so importing this module has no side effects).

    Settings come from the environment / .env unless passed in, as tests do.
    """
    if settings is None:
        load_dotenv()
        settings = Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = ConnectionPool(settings.database_url, min_size=1, max_size=10,
                              kwargs={"row_factory": dict_row}, open=True)
        with pool.connection() as conn:
            db.init_schema(conn)
            if n := db.fail_interrupted_jobs(conn):
                log.warning("Marked %d interrupted job(s) as failed", n)
        app.state.pool = pool
        app.state.runner = JobRunner(pool, settings.output_dir, settings.max_concurrent_jobs)
        yield
        pool.close()

    app = FastAPI(title="CCTV Incident Summariser", version="0.3.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    def require_job(conn: psycopg.Connection, job_id: str) -> dict:
        job = db.get_job(conn, job_id)
        if job is None:
            raise HTTPException(404, f"Job {job_id} not found")
        return job

    def frame_url(frame_path: str) -> str:
        rel = Path(frame_path).resolve().relative_to(settings.output_dir.resolve())
        return f"/frames/{rel.as_posix()}"

    @app.get("/health")
    def health(conn: Conn) -> dict:
        conn.execute("SELECT 1")
        return {"status": "ok"}

    @app.post("/jobs", status_code=202, response_model=JobCreated)
    def create_job(
        request: Request,
        background: BackgroundTasks,
        conn: Conn,
        video: UploadFile = File(..., description="CCTV clip (mp4, mov, avi, mkv, webm)"),
        sampling: Literal["hybrid", "scene", "interval"] = Form("hybrid"),
        start_time: datetime | None = Form(None, description="Wall-clock recording start, ISO 8601"),
    ) -> JobCreated:
        """Upload a video and queue it for processing. Poll ``GET /jobs/{id}`` for progress."""
        ext = Path(video.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(415, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
        job_id = uuid.uuid4().hex[:12]
        dst = settings.upload_dir / job_id / f"source{ext}"
        try:
            save_upload(video.file, dst, settings.max_upload_mb * 1024 * 1024)
            ingest.probe(dst)  # reject non-video files now, not minutes later in the background
        except UploadTooLarge as exc:
            raise HTTPException(413, str(exc)) from exc
        except ingest.IngestError as exc:
            shutil.rmtree(dst.parent, ignore_errors=True)
            raise HTTPException(422, f"Not a readable video: {exc}") from exc

        db.create_job(conn, job_id, video.filename or dst.name)
        background.add_task(request.app.state.runner.process, job_id, dst,
                            sampling=sampling, recording_start=start_time)
        return JobCreated(job_id=job_id, status="queued")

    @app.get("/jobs/{job_id}", response_model=JobStatus)
    def get_job(job_id: JobId, conn: Conn) -> JobStatus:
        """Job status with per-stage progress."""
        job = require_job(conn, job_id)
        progress, stages = stage_progress(job["status"], job["failed_stage"])
        return JobStatus(job_id=job["id"], progress=progress, stages=stages,
                         **{k: job[k] for k in ("source", "status", "error", "failed_stage", "meta",
                                                "sampling", "timings", "created_at", "updated_at")})

    @app.get("/jobs/{job_id}/events", response_model=list[EventOut])
    def get_events(job_id: JobId, conn: Conn) -> list[EventOut]:
        """All detections for a job, ordered by time."""
        require_job(conn, job_id)
        return [EventOut(frame_url=frame_url(e.pop("frame_path")), **e) for e in db.get_events(conn, job_id)]

    @app.get("/jobs/{job_id}/report", response_model=ReportOut)
    def get_report(job_id: JobId, conn: Conn) -> ReportOut:
        """The LLM incident report; 409 while the job is still running."""
        job = require_job(conn, job_id)
        report = db.get_report(conn, job_id)
        if report is None:
            if job["status"] not in ("done", "failed"):
                raise HTTPException(409, f"Report not ready (status: {job['status']})")
            raise HTTPException(404, "No report for this job")
        return ReportOut(**report)

    @app.get("/jobs/{job_id}/video")
    def get_video(job_id: JobId) -> FileResponse:
        """The normalised 720p H.264 video (supports HTTP range requests for seeking)."""
        path = settings.output_dir / job_id / "normalised.mp4"
        if not path.is_file():
            raise HTTPException(404, "Video not available yet")
        return FileResponse(path, media_type="video/mp4")

    @app.get("/frames/{frame_path:path}")
    def get_frame(frame_path: str) -> FileResponse:
        """A saved keyframe JPEG, e.g. ``/frames/<job_id>/frames/frame_000024.jpg``."""
        root = settings.output_dir.resolve()
        path = (root / frame_path).resolve()
        if not path.is_relative_to(root) or path.suffix != ".jpg" or not path.is_file():
            raise HTTPException(404, "Frame not found")  # same answer for traversal attempts
        return FileResponse(path, media_type="image/jpeg")

    return app
