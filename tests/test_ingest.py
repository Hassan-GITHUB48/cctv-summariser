import shutil
from pathlib import Path

import pytest

from pipeline.ingest import IngestError, probe, transcode

pytestmark = pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffmpeg not installed")


def test_probe_reads_metadata(synthetic_clip: Path) -> None:
    meta = probe(synthetic_clip)
    assert (meta.width, meta.height) == (1920, 1080)
    assert meta.fps == 25.0
    assert meta.codec == "h264"
    assert meta.duration_s == pytest.approx(12.0, abs=0.1)


def test_transcode_downscales_to_720p(synthetic_clip: Path, tmp_path: Path) -> None:
    out = transcode(synthetic_clip, tmp_path / "out.mp4")
    meta = probe(out)
    assert (meta.width, meta.height) == (1280, 720)
    assert meta.codec == "h264"
    assert meta.duration_s == pytest.approx(12.0, abs=0.1)


def test_transcode_never_upscales(synthetic_clip: Path, tmp_path: Path) -> None:
    small = transcode(synthetic_clip, tmp_path / "small.mp4", height=360)
    again = transcode(small, tmp_path / "again.mp4", height=720)
    assert probe(again).height == 360


def test_probe_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="not found"):
        probe(tmp_path / "nope.mp4")


def test_probe_non_video_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.mp4"
    bogus.write_text("not a video")
    with pytest.raises(IngestError):
        probe(bogus)
