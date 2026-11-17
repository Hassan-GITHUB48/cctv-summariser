import shutil
from pathlib import Path

import pytest

from pipeline.keyframes import extract, interval_frame_indices

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_scene_mode_finds_one_frame_per_segment(synthetic_clip: Path, tmp_path: Path) -> None:
    frames = extract(synthetic_clip, tmp_path, mode="scene")
    # Three 4 s segments -> three scenes, each sampled at its midpoint.
    assert [round(f.timestamp_s) for f in frames] == [2, 6, 10]
    assert all(f.path.exists() and f.path.stat().st_size > 0 for f in frames)


def test_interval_mode_samples_every_n_seconds(synthetic_clip: Path, tmp_path: Path) -> None:
    frames = extract(synthetic_clip, tmp_path, mode="interval", interval_s=3.0)
    assert [f.timestamp_s for f in frames] == [0.0, 3.0, 6.0, 9.0]


def test_interval_indices_math() -> None:
    assert interval_frame_indices(fps=25, frame_count=100, interval_s=1.0) == [0, 25, 50, 75]
    assert interval_frame_indices(fps=10, frame_count=3, interval_s=0.01) == [0, 1, 2]  # step >= 1


def test_invalid_inputs_raise(synthetic_clip: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        interval_frame_indices(fps=25, frame_count=100, interval_s=0)
    with pytest.raises(ValueError):
        extract(synthetic_clip, tmp_path, mode="bogus")  # type: ignore[arg-type]
