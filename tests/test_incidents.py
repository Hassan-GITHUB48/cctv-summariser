from datetime import datetime

from pipeline.incidents import group_events


def ev(t: float, label: str = "person", conf: float = 0.8) -> dict:
    return {"timestamp_s": t, "frame_index": int(t * 10), "label": label, "confidence": conf,
            "bbox": (0, 0, 10, 10), "frame_path": f"frames/{t}.jpg"}


def test_merges_close_sightings_and_splits_on_gaps() -> None:
    events = [ev(10), ev(12), ev(14), ev(30), ev(32)]  # 16 s gap > 5 s merge gap
    cands = group_events(events, video_duration_s=60)
    assert [(c.start_s, c.end_s, c.keyframes) for c in cands] == [(10, 14, 3), (30, 32, 2)]
    assert [c.id for c in cands] == ["C1", "C2"]


def test_labels_are_grouped_separately() -> None:
    cands = group_events([ev(10), ev(10, "car"), ev(12, "car")], video_duration_s=60)
    assert {(c.label, c.keyframes) for c in cands} == {("person", 1), ("car", 2)}
    assert "vehicle_visit" in next(c for c in cands if c.label == "car").flags


def test_prolonged_presence_and_group_flags() -> None:
    long_stay = [ev(t) for t in range(10, 46, 2)]  # 10..44 s = 34 s
    crowd = [ev(50, conf=c) for c in (0.9, 0.8, 0.7)]  # three people in one frame
    cands = group_events(long_stay + crowd, video_duration_s=120)
    assert "prolonged_presence" in cands[0].flags
    assert cands[1].max_count == 3 and "group" in cands[1].flags
    assert cands[1].peak_confidence == 0.9


def test_edge_flags() -> None:
    cands = group_events([ev(1), ev(58)], video_duration_s=60)
    assert "present_at_start" in cands[0].flags
    assert "present_at_end" in cands[1].flags


def test_unusual_hour_uses_wall_clock_and_wraps_midnight() -> None:
    late = group_events([ev(10)], video_duration_s=60, recording_start=datetime(2026, 1, 1, 23, 30))
    day = group_events([ev(10)], video_duration_s=60, recording_start=datetime(2026, 1, 1, 14, 0))
    assert "unusual_hour" in late[0].flags and late[0].wall_start == "2026-01-01T23:30:10"
    assert "unusual_hour" not in day[0].flags


def test_no_events_gives_no_candidates() -> None:
    assert group_events([], video_duration_s=60) == []
