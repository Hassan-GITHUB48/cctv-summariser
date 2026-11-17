"""Upload handling, stage-progress mapping and the background job runner."""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import BinaryIO

from psycopg_pool import ConnectionPool

from api.schemas import Stage
from pipeline import run

log = logging.getLogger(__name__)

STAGES = ("ingesting", "keyframes", "detecting", "reporting")
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
CHUNK = 1024 * 1024


class UploadTooLarge(Exception):
    """Raised when an upload exceeds the configured size limit."""


def save_upload(src: BinaryIO, dst: Path, max_bytes: int) -> int:
    """Copy an uploaded file to ``dst`` in 1 MB chunks, enforcing ``max_bytes``. Returns bytes written."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dst.open("wb") as out:
        while chunk := src.read(CHUNK):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                dst.unlink(missing_ok=True)
                raise UploadTooLarge(f"Upload exceeds {max_bytes // CHUNK} MB")
            out.write(chunk)
    return written


def stage_progress(status: str, failed_stage: str | None = None) -> tuple[float, list[Stage]]:
    """Map a job's status to per-stage states and overall progress (0..1).

    Stages before the current one are done, the current one is running (or
    failed, using ``failed_stage``), later ones are pending.
    """
    if status == "done":
        return 1.0, [Stage(name=s, state="done") for s in STAGES]
    if status == "queued" or (status == "failed" and failed_stage not in STAGES):
        state = "failed" if status == "failed" else "pending"
        return 0.0, [Stage(name=s, state=state if i == 0 else "pending") for i, s in enumerate(STAGES)]
    current = STAGES.index(failed_stage if status == "failed" else status)
    here = "failed" if status == "failed" else "running"
    states = ["done"] * current + [here] + ["pending"] * (len(STAGES) - current - 1)
    return round(current / len(STAGES), 2), [Stage(name=s, state=st) for s, st in zip(STAGES, states)]


class JobRunner:
    """Runs pipeline jobs in background threads, at most ``max_concurrent`` at a time.

    Extra jobs wait on the semaphore and stay ``queued``. YOLO and FFmpeg are
    CPU/GPU heavy, so running many jobs at once would only make each slower.
    """

    def __init__(self, pool: ConnectionPool, output_dir: Path, max_concurrent: int = 1) -> None:
        self.pool = pool
        self.output_dir = output_dir
        self._slots = threading.Semaphore(max_concurrent)

    def process(self, job_id: str, video: Path, **options) -> None:
        """Run one job end to end; errors are recorded on the job row, never raised."""
        with self._slots, self.pool.connection() as conn:
            try:
                run.run_with_db(conn, job_id, video, create_job=False, out_root=self.output_dir, **options)
                log.info("Job %s done", job_id)
            except Exception:  # run_with_db already marked the job failed
                log.exception("Job %s failed", job_id)
            finally:
                shutil.rmtree(video.parent, ignore_errors=True)  # normalised copy lives in output/
