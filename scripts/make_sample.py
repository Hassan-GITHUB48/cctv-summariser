"""Generate a synthetic 1080p test clip with known hard cuts using only FFmpeg.

The clip is made of three visually distinct segments joined by hard cuts, so
scene detection should find a boundary at every multiple of ``--segment``
seconds. Synthetic shapes won't trigger YOLO, so this tests pipeline mechanics;
use real public footage for detection quality.

Usage:
    python scripts/make_sample.py samples/synthetic.mp4 --segment 4
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

SIZE = "1920x1080"
FPS = 25


def make_sample(dst: Path, segment_s: float = 4.0) -> Path:
    """Write a 3-segment synthetic clip to ``dst`` and return its path."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = f"size={SIZE}:rate={FPS}:duration={segment_s}"
    graph = (
        f"testsrc2={src}[a];"
        f"smptebars={src}[b];"
        f"color=c=navy:{src}[bg];"
        f"color=c=orange:size=200x200:rate={FPS}:duration={segment_s}[box];"
        "[bg][box]overlay=x='t*300':y=440[c];"  # moving box: motion within one scene
        "[a][b][c]concat=n=3:v=1:a=0[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-filter_complex", graph, "-map", "[out]",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, nargs="?", default=Path("samples/synthetic.mp4"))
    parser.add_argument("--segment", type=float, default=4.0, help="seconds per segment")
    args = parser.parse_args()
    path = make_sample(args.output, args.segment)
    print(f"Wrote {path} (cuts at {args.segment:g}s and {2 * args.segment:g}s)")


if __name__ == "__main__":
    main()
