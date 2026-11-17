import type { DetectionEvent } from '../api'

/** Evenly spaced axis ticks with a "nice" step (1, 2, 5, 10, 15, 30, 60 s...), about `target` of them. */
export function ticks(duration: number, target = 8): number[] {
  if (duration <= 0) return [0]
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
  const step = steps.find((s) => duration / s <= target) ?? 900
  const out: number[] = []
  for (let t = 0; t <= duration + 1e-9; t += step) out.push(t)
  return out
}

export interface Marker {
  label: string
  timestamp_s: number
  count: number // detections of this label in this keyframe
  maxConfidence: number
}

/** One marker per (label, keyframe), counting how many objects of that label the frame contains. */
export function markersByLabel(events: DetectionEvent[]): Map<string, Marker[]> {
  const byKey = new Map<string, Marker>()
  for (const e of events) {
    const key = `${e.label}@${e.timestamp_s}`
    const m = byKey.get(key)
    if (m) {
      m.count += 1
      m.maxConfidence = Math.max(m.maxConfidence, e.confidence)
    } else {
      byKey.set(key, { label: e.label, timestamp_s: e.timestamp_s, count: 1, maxConfidence: e.confidence })
    }
  }
  const lanes = new Map<string, Marker[]>()
  for (const m of byKey.values()) lanes.set(m.label, [...(lanes.get(m.label) ?? []), m])
  for (const list of lanes.values()) list.sort((a, b) => a.timestamp_s - b.timestamp_s)
  return lanes
}
