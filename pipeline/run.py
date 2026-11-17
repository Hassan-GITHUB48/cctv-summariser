"""CLI that chains ingest -> keyframes -> detect -> report, stores results in Postgres and output/<job_id>/.

Usage:
    python -m pipeline.run samples/clip.mp4 [--sampling hybrid|scene|interval] [--no-db] [--no-report]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

import psycopg
from dotenv import load_dotenv

from pipeline import db, detect, incidents, ingest, keyframes, report

log = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]


@contextmanager
def timed(timings: dict[str, float], stage: str) -> Iterator[None]:
    """Record the wall-clock duration of the enclosed block in ``timings[stage]``."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] = round(time.perf_counter() - start, 3)


def run_pipeline(
    video: Path,
    out_root: Path = Path("output"),
    sampling: keyframes.SamplingMode = "hybrid",
    interval_s: float = 2.0,
    max_gap_s: float = 2.0,
    conf: float = 0.4,
    device: str | None = None,
    job_id: str | None = None,
    recording_start: datetime | None = None,
    with_report: bool = True,
    on_status: StatusCallback | None = None,
) -> dict:
    """Run all stages on ``video`` and return (and save to ``out_root/job_id``) the job result.

    ``on_status`` is called with the stage name as each stage starts, so callers
    (CLI, API background task) can track progress without the pipeline knowing about them.
    """
    job_id = job_id or uuid.uuid4().hex[:8]
    job_dir = out_root / job_id
    status = on_status or (lambda _: None)
    timings: dict[str, float] = {}
    if with_report:
        report.check_credentials()

    status("ingesting")
    with timed(timings, "ingest"):
        meta = ingest.probe(video)
        normalised = ingest.transcode(video, job_dir / "normalised.mp4")
    status("keyframes")
    with timed(timings, "keyframes"):
        frames = keyframes.extract(
            normalised, job_dir / "frames", sampling, interval_s=interval_s, max_gap_s=max_gap_s
        )
    status("detecting")
    with timed(timings, "detect"):
        events = [e.to_dict() for e in detect.detect(frames, conf=conf, device=device)]

    sampling_info = {
        "mode": sampling,
        "interval_s": interval_s if sampling == "interval" else None,
        "max_gap_s": max_gap_s if sampling == "hybrid" else None,
    }
    candidates = incidents.group_events(events, meta.duration_s, recording_start=recording_start)
    result = {
        "job_id": job_id,
        "source": str(video),
        "source_meta": meta.to_dict(),
        "sampling": sampling_info,
        "conf_threshold": conf,
        "timings_s": timings,
        "keyframes": [k.to_dict() for k in frames],
        "events": events,
        "candidates": [c.to_dict() for c in candidates],
        "report": None,
    }
    if with_report:
        status("reporting")
        with timed(timings, "report"):
            rep, model = report.generate_report(candidates, meta.to_dict(), sampling_info)
        result["report"] = {"model": model, **rep.model_dump()}

    (job_dir / "events.json").write_text(json.dumps(result, indent=2))
    log.info("Wrote %s", job_dir / "events.json")
    return result


def run_with_db(
    conn: psycopg.Connection, job_id: str, video: Path, create_job: bool = True, **kwargs
) -> dict:
    """Run the pipeline as a tracked job: status updates, then events and report persisted.

    Pass ``create_job=False`` when the job row already exists (e.g. created by the API).
    On any failure the job is marked ``failed`` with the error message and the exception re-raised.
    """
    if create_job:
        db.create_job(conn, job_id, str(video))
    try:
        result = run_pipeline(
            video, job_id=job_id, on_status=lambda s: db.update_job(conn, job_id, status=s), **kwargs
        )
    except Exception as exc:
        db.update_job(conn, job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    db.insert_events(conn, job_id, result["events"])
    if rep := result["report"]:
        db.save_report(conn, job_id, rep["model"], rep["summary"], rep["incidents"])
    db.update_job(
        conn, job_id, status="done", meta=result["source_meta"],
        sampling=result["sampling"], timings=result["timings_s"],
    )
    return result


def _mmss(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def print_summary(result: dict, out_root: Path) -> None:
    """Print a human-readable summary of a pipeline result to stdout."""
    meta = result["source_meta"]
    counts = Counter(e["label"] for e in result["events"])
    frames_with_hits = len({e["frame_index"] for e in result["events"]})
    print(f"\nJob {result['job_id']}  ({result['source']})")
    print(f"  Source:     {meta['width']}x{meta['height']} {meta['codec']} "
          f"@ {meta['fps']:g} fps, {meta['duration_s']:.1f}s")
    print(f"  Sampling:   {result['sampling']['mode']} -> {len(result['keyframes'])} keyframes "
          f"({frames_with_hits} with detections)")
    print(f"  Detections ({len(result['events'])}): "
          + (", ".join(f"{label}={n}" for label, n in counts.most_common()) or "none"))
    print(f"  Candidates: {len(result['candidates'])}")
    print("  Timings:    " + ", ".join(f"{k} {v:.2f}s" for k, v in result["timings_s"].items())
          + f" (total {sum(result['timings_s'].values()):.2f}s)")
    if rep := result["report"]:
        print(f"\n  Report ({rep['model']}): {rep['summary']}")
        for inc in rep["incidents"]:
            print(f"   [sev {inc['severity']}] {_mmss(inc['start_s'])}-{_mmss(inc['end_s'])} "
                  f"{inc['title']} -> {inc['recommended_action']}")
    print(f"\n  Output:     {out_root / result['job_id'] / 'events.json'}\n")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the CCTV analytics pipeline on a video.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--sampling", choices=["hybrid", "scene", "interval"], default="hybrid")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between frames (interval mode)")
    parser.add_argument("--max-gap", type=float, default=2.0, help="max seconds between frames (hybrid mode)")
    parser.add_argument("--conf", type=float, default=0.4, help="detection confidence threshold")
    parser.add_argument("--device", default=None, help="torch device, e.g. cpu or mps (default: auto)")
    parser.add_argument("--start-time", type=datetime.fromisoformat, default=None,
                        help="wall-clock recording start (ISO 8601), enables unusual-hour flags")
    parser.add_argument("--no-report", action="store_true", help="skip the LLM report stage")
    parser.add_argument("--no-db", action="store_true", help="don't store results in Postgres")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pyscenedetect").setLevel(args.log_level.upper())  # it logs INFO by default
    kwargs = dict(
        out_root=args.out, sampling=args.sampling, interval_s=args.interval, max_gap_s=args.max_gap,
        conf=args.conf, device=args.device, recording_start=args.start_time, with_report=not args.no_report,
    )
    job_id = uuid.uuid4().hex[:8]
    try:
        if args.no_db:
            result = run_pipeline(args.video, job_id=job_id, **kwargs)
        else:
            with db.connect() as conn:
                db.init_schema(conn)
                result = run_with_db(conn, job_id, args.video, **kwargs)
    except (ingest.IngestError, report.ReportError, psycopg.OperationalError, RuntimeError) as exc:
        raise SystemExit(f"Error (job {job_id}): {exc}") from exc
    print_summary(result, args.out)


if __name__ == "__main__":
    main()
