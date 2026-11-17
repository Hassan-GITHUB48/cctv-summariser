import json
import shutil
from pathlib import Path

import pytest

from pipeline.run import run_pipeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.mark.parametrize(("sampling", "n_frames"), [("scene", 3), ("interval", 6), ("hybrid", 6)])
def test_pipeline_writes_events_json(
    synthetic_clip: Path, tmp_path: Path, sampling: str, n_frames: int
) -> None:
    result = run_pipeline(synthetic_clip, out_root=tmp_path, sampling=sampling, job_id="job1")
    job_dir = tmp_path / "job1"

    assert (job_dir / "normalised.mp4").exists()
    assert json.loads((job_dir / "events.json").read_text()) == result
    assert set(result["timings_s"]) == {"ingest", "keyframes", "detect"}
    assert result["sampling"]["mode"] == sampling
    assert len(result["keyframes"]) == n_frames
    assert all(Path(k["path"]).exists() for k in result["keyframes"])
