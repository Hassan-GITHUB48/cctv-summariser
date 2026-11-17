"""Stage 2: pick representative frames by scene-change detection or fixed-interval sampling."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import cv2
from scenedetect import ContentDetector, detect

log = logging.getLogger(__name__)

SamplingMode = Literal["scene", "interval"]


@dataclass(frozen=True)
class Keyframe:
    """A saved frame and where it sits in the video."""

    frame_index: int
    timestamp_s: float
    path: Path

    def to_dict(self) -> dict:
        return {**asdict(self), "path": str(self.path)}


def scene_frame_indices(video: Path, threshold: float = 27.0) -> list[int]:
    """Return the middle frame index of each scene found by ContentDetector.

    The middle frame avoids the blur/fade often present right at a cut.
    ``start_in_scene=True`` makes a cut-free video count as one scene.
    """
    scenes = detect(str(video), ContentDetector(threshold=threshold), start_in_scene=True)
    log.info("Detected %d scenes in %s", len(scenes), video.name)
    return [(start.frame_num + end.frame_num) // 2 for start, end in scenes]


def interval_frame_indices(fps: float, frame_count: int, interval_s: float) -> list[int]:
    """Return one frame index every ``interval_s`` seconds, starting at frame 0."""
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    step = max(1, round(fps * interval_s))
    return list(range(0, frame_count, step))


def save_frames(video: Path, indices: list[int], out_dir: Path) -> list[Keyframe]:
    """Decode the given frame indices from ``video`` and save them as JPEGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    keyframes: list[Keyframe] = []
    try:
        for idx in sorted(set(indices)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)  # seeks to nearest keyframe, then decodes forward
            ok, frame = cap.read()
            if not ok:
                log.warning("Could not read frame %d from %s", idx, video.name)
                continue
            path = out_dir / f"frame_{idx:06d}.jpg"
            cv2.imwrite(str(path), frame)
            keyframes.append(Keyframe(idx, round(idx / fps, 3), path))
    finally:
        cap.release()
    return keyframes


def extract(
    video: Path,
    out_dir: Path,
    mode: SamplingMode = "scene",
    interval_s: float = 2.0,
    threshold: float = 27.0,
) -> list[Keyframe]:
    """Select frames from ``video`` with the chosen sampling mode and save them to ``out_dir``."""
    if mode == "scene":
        indices = scene_frame_indices(video, threshold)
    elif mode == "interval":
        cap = cv2.VideoCapture(str(video))
        fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        indices = interval_frame_indices(fps, count, interval_s)
    else:
        raise ValueError(f"Unknown sampling mode: {mode}")
    keyframes = save_frames(video, indices, out_dir)
    log.info("Saved %d keyframes (%s mode) to %s", len(keyframes), mode, out_dir)
    return keyframes
