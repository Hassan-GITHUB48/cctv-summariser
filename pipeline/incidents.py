"""Group per-frame detections into candidate incidents with deterministic rules.

The LLM never sees raw detections: it gets these compact, pre-computed
candidates, which keeps prompts small and every claim traceable to evidence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

VEHICLES = {"car", "truck", "motorcycle", "bicycle"}


@dataclass
class Candidate:
    """A continuous window in which one object class was visible."""

    id: str
    label: str
    start_s: float
    end_s: float
    keyframes: int              # keyframes in the window where the label was detected
    max_count: int              # most instances of the label seen in a single frame
    peak_confidence: float
    frame_path: str             # frame with the highest-confidence detection
    flags: list[str] = field(default_factory=list)
    wall_start: str | None = None
    wall_end: str | None = None

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 3)

    def to_dict(self) -> dict:
        return {**asdict(self), "duration_s": self.duration_s}


def _windows(timestamps: list[float], merge_gap_s: float) -> list[list[float]]:
    """Split sorted timestamps into runs where consecutive gaps are <= ``merge_gap_s``."""
    runs: list[list[float]] = []
    for t in timestamps:
        if runs and t - runs[-1][-1] <= merge_gap_s:
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def _in_quiet_hours(moment: datetime, quiet_hours: tuple[int, int]) -> bool:
    start, end = quiet_hours  # e.g. (22, 6) wraps past midnight
    h = moment.hour
    return start <= h < end if start < end else h >= start or h < end


def group_events(
    events: list[dict],
    video_duration_s: float,
    merge_gap_s: float = 5.0,
    loiter_s: float = 30.0,
    group_size: int = 3,
    recording_start: datetime | None = None,
    quiet_hours: tuple[int, int] = (22, 6),
) -> list[Candidate]:
    """Turn detection events into candidate incidents, sorted by start time.

    Detections of the same label are merged into one window while the gap
    between sightings is at most ``merge_gap_s`` (tolerates a missed frame or
    two). Each window is then flagged by simple rules: prolonged person
    presence, groups of people, vehicle arrival/departure, and activity in
    quiet hours when the recording's wall-clock start is known.
    """
    by_label: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for e in events:
        by_label[e["label"]][e["timestamp_s"]].append(e)

    candidates: list[Candidate] = []
    edge_s = merge_gap_s  # windows this close to either end may have started/ended off-camera
    for label, frames in by_label.items():
        for run in _windows(sorted(frames), merge_gap_s):
            dets = [d for t in run for d in frames[t]]
            best = max(dets, key=lambda d: d["confidence"])
            c = Candidate(
                id="", label=label, start_s=run[0], end_s=run[-1], keyframes=len(run),
                max_count=max(len(frames[t]) for t in run),
                peak_confidence=best["confidence"], frame_path=best["frame_path"],
            )
            if label == "person" and c.duration_s >= loiter_s:
                c.flags.append("prolonged_presence")
            if label == "person" and c.max_count >= group_size:
                c.flags.append("group")
            if label in VEHICLES:
                c.flags.append("vehicle_visit")
            if c.start_s <= edge_s:
                c.flags.append("present_at_start")
            if c.end_s >= video_duration_s - edge_s:
                c.flags.append("present_at_end")
            if recording_start is not None:
                start = recording_start + timedelta(seconds=c.start_s)
                end = recording_start + timedelta(seconds=c.end_s)
                c.wall_start, c.wall_end = start.isoformat(), end.isoformat()
                if _in_quiet_hours(start, quiet_hours) or _in_quiet_hours(end, quiet_hours):
                    c.flags.append("unusual_hour")
            candidates.append(c)

    candidates.sort(key=lambda c: (c.start_s, c.label))
    for i, c in enumerate(candidates, start=1):
        c.id = f"C{i}"
    return candidates
