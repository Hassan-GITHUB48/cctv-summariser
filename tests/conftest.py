"""Shared fixtures: one synthetic clip per test session."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.make_sample import make_sample

SEGMENT_S = 4.0  # synthetic clip has hard cuts at 4s and 8s, total 12s


@pytest.fixture(scope="session")
def synthetic_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 12 s 1080p clip with three distinct segments."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    return make_sample(tmp_path_factory.mktemp("clips") / "synthetic.mp4", SEGMENT_S)
