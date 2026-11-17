"""Stage 1: probe video metadata with ffprobe and normalise to 720p H.264 with ffmpeg."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path

log = logging.getLogger(__name__)


class IngestError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails or the input has no video stream."""


@dataclass(frozen=True)
class VideoMeta:
    """Basic properties of a video file's first video stream."""

    duration_s: float
    fps: float
    width: int
    height: int
    codec: str

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command, raising IngestError with the tail of stderr on failure."""
    log.debug("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise IngestError(f"{cmd[0]} failed (exit {proc.returncode}): {tail}")
    return proc


def probe(path: Path) -> VideoMeta:
    """Return metadata for the first video stream in ``path`` using ffprobe."""
    if not path.exists():
        raise IngestError(f"File not found: {path}")
    proc = _run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ])
    info = json.loads(proc.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise IngestError(f"No video stream in {path}")

    # avg_frame_rate is the real average; r_frame_rate can be a timebase guess on VFR footage.
    rate = video.get("avg_frame_rate", "0/0")
    if rate in ("0/0", ""):
        rate = video["r_frame_rate"]
    return VideoMeta(
        duration_s=float(info["format"].get("duration", video.get("duration", 0.0))),
        fps=round(float(Fraction(rate)), 3),
        width=int(video["width"]),
        height=int(video["height"]),
        codec=video["codec_name"],
    )


def transcode(src: Path, dst: Path, height: int = 720) -> Path:
    """Normalise ``src`` to H.264 at most ``height`` px tall, without audio.

    Never upscales; width is computed to keep aspect ratio (rounded to even, as
    H.264 with yuv420p requires). ``+faststart`` moves the index to the front so
    browsers can start playback before the whole file downloads.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-vf", f"scale=-2:'min({height},ih)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(dst),
    ])
    log.info("Transcoded %s -> %s", src, dst)
    return dst
