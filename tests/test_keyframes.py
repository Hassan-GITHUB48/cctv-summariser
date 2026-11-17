import shutil
from pathlib import Path

import pytest

from pipeline.keyframes import extract, fill_gaps, interval_frame_indices

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


def _max_gap_with_edges(indices: list[int], frame_count: int) -> int:
    points = [-1, *indices, frame_count]  # gaps from the start/end of the video count too
    return max(b - a - 1 for a, b in zip(points, points[1:]))


@pytest.mark.parametrize(
    ("scenes", "frame_count", "max_gap"),
    [([125], 300, 50), ([50, 150, 250], 300, 75), ([], 120, 50), ([0, 299], 300, 50), ([0], 1, 50)],
)
def test_fill_gaps_keeps_scenes_and_bounds_gaps(scenes: list[int], frame_count: int, max_gap: int) -> None:
    out = fill_gaps(scenes, frame_count, max_gap)
    assert set(scenes) <= set(out)
    assert out == sorted(set(out))
    assert all(0 <= i < frame_count for i in out)
    assert _max_gap_with_edges(out, frame_count) < max_gap


def test_fill_gaps_example() -> None:
    # One scene midpoint at 125, 2 s gap at 25 fps over 12 s: fillers before and after it.
    assert fill_gaps([125], 300, 50) == [0, 50, 100, 125, 175, 225, 275]


def test_hybrid_mode_adds_frames_between_scenes(synthetic_clip: Path, tmp_path: Path) -> None:
    frames = extract(synthetic_clip, tmp_path, mode="hybrid", max_gap_s=3.0)
    indices = [f.frame_index for f in frames]
    assert {50, 150, 250} <= set(indices)  # scene midpoints are kept
    assert len(indices) > 3
    assert max(b - a for a, b in zip(indices, indices[1:])) <= 75  # 3 s at 25 fps


def test_invalid_inputs_raise(synthetic_clip: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        interval_frame_indices(fps=25, frame_count=100, interval_s=0)
    with pytest.raises(ValueError):
        fill_gaps([10], frame_count=100, max_gap=0)
    with pytest.raises(ValueError):
        extract(synthetic_clip, tmp_path, mode="bogus")  # type: ignore[arg-type]
