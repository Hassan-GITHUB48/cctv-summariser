"""CLI that chains ingest -> keyframes -> detect and writes output/<job_id>/events.json.

Usage:
    python -m pipeline.run samples/clip.mp4 [--sampling hybrid|scene|interval]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pipeline import detect, ingest, keyframes

log = logging.getLogger(__name__)


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
) -> dict:
    """Run all stages on ``video`` and return (and save) the job result."""
    job_id = job_id or uuid.uuid4().hex[:8]
    job_dir = out_root / job_id
    timings: dict[str, float] = {}

    with timed(timings, "ingest"):
        meta = ingest.probe(video)
        normalised = ingest.transcode(video, job_dir / "normalised.mp4")
    with timed(timings, "keyframes"):
        frames = keyframes.extract(
            normalised, job_dir / "frames", sampling, interval_s=interval_s, max_gap_s=max_gap_s
        )
    with timed(timings, "detect"):
        events = detect.detect(frames, conf=conf, device=device)

    result = {
        "job_id": job_id,
        "source": str(video),
        "source_meta": meta.to_dict(),
        "sampling": {
            "mode": sampling,
            "interval_s": interval_s if sampling == "interval" else None,
            "max_gap_s": max_gap_s if sampling == "hybrid" else None,
        },
        "conf_threshold": conf,
        "timings_s": timings,
        "keyframes": [k.to_dict() for k in frames],
        "events": [e.to_dict() for e in events],
    }
    (job_dir / "events.json").write_text(json.dumps(result, indent=2))
    log.info("Wrote %s", job_dir / "events.json")
    return result


def print_summary(result: dict, out_root: Path) -> None:
    """Print a human-readable summary of a pipeline result to stdout."""
    meta = result["source_meta"]
    counts = Counter(e["label"] for e in result["events"])
    frames_with_hits = len({e["frame_index"] for e in result["events"]})
    print(f"\nJob {result['job_id']}  ({result['source']})")
    print(f"  Source:    {meta['width']}x{meta['height']} {meta['codec']} "
          f"@ {meta['fps']:g} fps, {meta['duration_s']:.1f}s")
    print(f"  Sampling:  {result['sampling']['mode']} -> {len(result['keyframes'])} keyframes "
          f"({frames_with_hits} with detections)")
    print(f"  Detections ({len(result['events'])}): "
          + (", ".join(f"{label}={n}" for label, n in counts.most_common()) or "none"))
    print("  Timings:   " + ", ".join(f"{k} {v:.2f}s" for k, v in result["timings_s"].items())
          + f" (total {sum(result['timings_s'].values()):.2f}s)")
    print(f"  Output:    {out_root / result['job_id'] / 'events.json'}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CCTV analytics pipeline on a video.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--sampling", choices=["hybrid", "scene", "interval"], default="hybrid")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between frames (interval mode)")
    parser.add_argument("--max-gap", type=float, default=2.0, help="max seconds between frames (hybrid mode)")
    parser.add_argument("--conf", type=float, default=0.4, help="detection confidence threshold")
    parser.add_argument("--device", default=None, help="torch device, e.g. cpu or mps (default: auto)")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pyscenedetect").setLevel(args.log_level.upper())  # it logs INFO by default
    try:
        result = run_pipeline(
            args.video, args.out, args.sampling, args.interval, args.max_gap, args.conf, args.device
        )
    except ingest.IngestError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print_summary(result, args.out)


if __name__ == "__main__":
    main()
