import json
from pathlib import Path

import pytest
import ultralytics

from pipeline.detect import TARGET_CLASSES, detect
from pipeline.keyframes import Keyframe

BUS = Path(ultralytics.__file__).parent / "assets" / "bus.jpg"  # bundled image: people + a bus


@pytest.fixture(scope="module")
def bus_keyframe() -> list[Keyframe]:
    return [Keyframe(frame_index=125, timestamp_s=5.0, path=BUS)]


def test_detects_people_and_filters_other_classes(bus_keyframe: list[Keyframe]) -> None:
    events = detect(bus_keyframe, conf=0.4)
    labels = {e.label for e in events}
    assert "person" in labels
    assert labels <= set(TARGET_CLASSES)  # "bus" is a COCO class but not a target
    assert all(e.confidence >= 0.4 for e in events)


def test_event_fields_and_json(bus_keyframe: list[Keyframe]) -> None:
    event = detect(bus_keyframe)[0]
    assert (event.timestamp_s, event.frame_index) == (5.0, 125)
    x1, y1, x2, y2 = event.bbox
    assert 0 <= x1 < x2 and 0 <= y1 < y2
    assert json.loads(json.dumps(event.to_dict()))["label"] == event.label


def test_higher_threshold_gives_fewer_or_equal_events(bus_keyframe: list[Keyframe]) -> None:
    assert len(detect(bus_keyframe, conf=0.85)) <= len(detect(bus_keyframe, conf=0.25))


def test_empty_input_returns_empty() -> None:
    assert detect([]) == []
