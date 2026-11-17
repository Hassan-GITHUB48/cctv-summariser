import { useMemo, useRef, useState, type MouseEvent } from 'react'
import type { DetectionEvent, Incident } from '../api'
import { classColor, orderedLabels } from '../lib/classes'
import { mmss, timeRange } from '../lib/format'
import { severityStyle } from '../lib/severity'
import { markersByLabel, ticks } from '../lib/timeline'

interface Props {
  duration: number
  events: DetectionEvent[]
  incidents: Incident[]
  currentTime: number
  onSeek: (t: number) => void
}

interface Tip {
  x: number // % across the track
  lane: number
  text: string
}

const LANE_H = 28

/**
 * Swim-lane timeline: an incidents lane (severity bands) above one lane per object class
 * (a marker per keyframe with detections). Every lane is labelled, so colour is never the
 * only cue. Click anywhere on a lane to seek; markers and bands seek to their start.
 */
export function Timeline({ duration, events, incidents, currentTime, onSeek }: Props) {
  const lanes = useMemo(() => markersByLabel(events), [events])
  const labels = useMemo(() => orderedLabels(lanes.keys()), [lanes])
  const axis = useMemo(() => ticks(duration), [duration])
  const trackRef = useRef<HTMLDivElement>(null)
  const [tip, setTip] = useState<Tip | null>(null)
  const pct = (t: number) => `${(Math.min(Math.max(t, 0), duration) / duration) * 100}%`

  function seekFromClick(e: MouseEvent<HTMLDivElement>) {
    const rect = trackRef.current?.getBoundingClientRect()
    if (!rect) return
    onSeek(((e.clientX - rect.left) / rect.width) * duration)
  }

  const laneNames = ['Incidents', ...labels]

  return (
    <div className="flex select-none px-4 pb-3 pt-2">
      {/* lane labels */}
      <div className="w-24 shrink-0 pt-5">
        {laneNames.map((name, i) => (
          <div key={name} style={{ height: LANE_H }} className="flex items-center gap-2 pr-2">
            {i > 0 && <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: classColor(name) }} />}
            <span className={`truncate text-[12.5px] ${i === 0 ? 'eyebrow' : 'capitalize text-ink-2'}`}>{name}</span>
          </div>
        ))}
      </div>

      {/* track */}
      <div ref={trackRef} className="relative min-w-0 flex-1">
        <div className="relative h-5 font-mono text-[10.5px] text-ink-3">
          {axis.map((t) => (
            <span key={t} className="absolute -translate-x-1/2" style={{ left: pct(t) }}>
              {mmss(t)}
            </span>
          ))}
        </div>

        <div className="relative" onMouseLeave={() => setTip(null)}>
          {axis.map((t) => (
            <div key={t} aria-hidden className="absolute inset-y-0 w-px bg-line/70" style={{ left: pct(t) }} />
          ))}

          {/* incidents lane */}
          <div className="relative cursor-pointer border-b border-line" style={{ height: LANE_H }} onClick={seekFromClick}>
            {incidents.map((inc, i) => {
              const sev = severityStyle(inc.severity)
              return (
                <button
                  key={i}
                  type="button"
                  aria-label={`Incident ${inc.title}, severity ${inc.severity}, at ${timeRange(inc.start_s, inc.end_s)}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSeek(inc.start_s)
                  }}
                  onMouseEnter={() => setTip({ x: ((inc.start_s + inc.end_s) / 2 / duration) * 100, lane: 0, text: `S${inc.severity} ${sev.label} · ${timeRange(inc.start_s, inc.end_s)} · ${inc.title}` })}
                  className="absolute top-1/2 h-4 min-w-2 -translate-y-1/2 rounded-sm border border-bg/60 focus-visible:outline-2 focus-visible:outline-ink"
                  style={{ left: pct(inc.start_s), width: `calc(${pct(inc.end_s)} - ${pct(inc.start_s)})`, background: sev.color }}
                />
              )
            })}
          </div>

          {/* one lane per class */}
          {labels.map((label, li) => (
            <div key={label} className="relative cursor-pointer border-b border-line/60 last:border-b-0" style={{ height: LANE_H }} onClick={seekFromClick}>
              {lanes.get(label)!.map((m) => (
                <button
                  key={m.timestamp_s}
                  type="button"
                  aria-label={`${m.count} ${label} at ${mmss(m.timestamp_s)}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSeek(m.timestamp_s)
                  }}
                  onMouseEnter={() => setTip({ x: (m.timestamp_s / duration) * 100, lane: li + 1, text: `${mmss(m.timestamp_s)} · ${m.count} ${label}${m.count > 1 ? 's' : ''} · ${Math.round(m.maxConfidence * 100)}%` })}
                  className="group absolute top-0 grid h-full w-3.5 -translate-x-1/2 place-items-center focus-visible:outline-2 focus-visible:outline-ink"
                  style={{ left: pct(m.timestamp_s) }}
                >
                  <span className="h-3 w-2 rounded-sm ring-2 ring-panel transition-transform group-hover:scale-125" style={{ background: classColor(label) }} />
                </button>
              ))}
            </div>
          ))}

          {/* playhead */}
          <div aria-hidden className="pointer-events-none absolute inset-y-0 w-px bg-ink" style={{ left: pct(currentTime) }}>
            <div className="absolute -top-1 -left-[3px] size-[7px] rounded-full bg-ink" />
          </div>

          {tip && (
            <div
              role="tooltip"
              className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded border border-line-strong bg-bg px-2 py-1 font-mono text-[11.5px] text-ink shadow-lg"
              style={{ left: `clamp(80px, ${tip.x}%, calc(100% - 80px))`, top: tip.lane * LANE_H - 2 }}
            >
              {tip.text}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
