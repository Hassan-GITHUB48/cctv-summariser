"""Stage 3: run YOLOv8 on keyframes and keep people/vehicles above a confidence threshold."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from ultralytics import YOLO

from pipeline.keyframes import Keyframe

log = logging.getLogger(__name__)

TARGET_CLASSES = ("person", "bicycle", "car", "motorcycle", "truck")
DEFAULT_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")


@dataclass(frozen=True)
class Event:
    """One detected object on one keyframe."""

    timestamp_s: float
    frame_index: int
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels
    frame_path: str

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=2)
def load_model(name: str = DEFAULT_MODEL) -> YOLO:
    """Load (and cache) a YOLO model; weights download on first use."""
    log.info("Loading YOLO model %s", name)
    return YOLO(name)


def detect(
    keyframes: list[Keyframe],
    conf: float = 0.4,
    model_name: str = DEFAULT_MODEL,
    device: str | None = None,
) -> list[Event]:
    """Detect target classes on each keyframe and return events sorted by time.

    Filtering by class inside ``predict`` (rather than afterwards) lets YOLO skip
    NMS work for the 75 COCO classes we don't care about.
    """
    if not keyframes:
        return []
    model = load_model(model_name)
    class_ids = [i for i, name in model.names.items() if name in TARGET_CLASSES]
    results = model.predict(
        [str(k.path) for k in keyframes],
        conf=conf, classes=class_ids, device=device, stream=True, verbose=False,
    )
    events: list[Event] = []
    for kf, result in zip(keyframes, results):
        for box in result.boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            events.append(Event(
                timestamp_s=kf.timestamp_s,
                frame_index=kf.frame_index,
                label=model.names[int(box.cls)],
                confidence=round(float(box.conf), 3),
                bbox=(x1, y1, x2, y2),
                frame_path=str(kf.path),
            ))
    log.info("Found %d detections on %d keyframes", len(events), len(keyframes))
    return sorted(events, key=lambda e: (e.timestamp_s, -e.confidence))
