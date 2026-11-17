import { useMemo, useState } from 'react'
import { api, type DetectionEvent } from '../api'
import { classColor } from '../lib/classes'
import { mmss } from '../lib/format'

interface Frame {
  url: string
  timestamp_s: number
  detections: DetectionEvent[]
}

function groupFrames(events: DetectionEvent[]): Frame[] {
  const frames = new Map<string, Frame>()
  for (const e of events) {
    const f = frames.get(e.frame_url) ?? { url: e.frame_url, timestamp_s: e.timestamp_s, detections: [] }
    f.detections.push(e)
    frames.set(e.frame_url, f)
  }
  return [...frames.values()].sort((a, b) => a.timestamp_s - b.timestamp_s)
}

/** A keyframe with its detections drawn as boxes. Box positions are % of the image's natural size. */
function FrameThumb({ frame, active, onSelect }: { frame: Frame; active: boolean; onSelect: () => void }) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [failed, setFailed] = useState(false)

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`Keyframe at ${mmss(frame.timestamp_s)}: ${frame.detections.map((d) => d.label).join(', ')}`}
      className={`group relative block overflow-hidden rounded-md border bg-black text-left focus-visible:outline-2 focus-visible:outline-ink ${active ? 'border-ink' : 'border-line hover:border-line-strong'}`}
    >
      {failed ? (
        <div className="grid aspect-video place-items-center text-[12px] text-ink-3">Frame unavailable</div>
      ) : (
        <img
          src={api.frameUrl(frame.url)}
          alt=""
          loading="lazy"
          className="block aspect-video w-full object-contain"
          onLoad={(e) => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
          onError={() => setFailed(true)}
        />
      )}
      {size &&
        frame.detections.map((d, i) => {
          const [x1, y1, x2, y2] = d.bbox
          // Keep the tag inside the frame: drop it inside the box near the top edge,
          // and right-align it near the right edge.
          const tagInside = y1 / size.h < 0.12
          const tagRight = x1 / size.w > 0.6
          return (
            <span
              key={i}
              className="pointer-events-none absolute rounded-[2px] border-[1.5px]"
              style={{
                left: `${(x1 / size.w) * 100}%`,
                top: `${(y1 / size.h) * 100}%`,
                width: `${((x2 - x1) / size.w) * 100}%`,
                height: `${((y2 - y1) / size.h) * 100}%`,
                borderColor: classColor(d.label),
              }}
            >
              <span
                className={`absolute whitespace-nowrap px-1 font-mono text-[9.5px] leading-[14px] text-white ${tagInside ? 'top-0 rounded-b-[2px]' : '-top-[15px] rounded-t-[2px]'} ${tagRight ? 'right-[-1.5px]' : 'left-[-1.5px]'}`}
                style={{ background: classColor(d.label) }}
              >
                {d.label} {Math.round(d.confidence * 100)}
              </span>
            </span>
          )
        })}
      <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10.5px] text-ink">
        {mmss(frame.timestamp_s)}
      </span>
    </button>
  )
}

/** Grid of keyframes that contain detections; the frame nearest the playhead is highlighted. */
export function FrameGallery({ events, currentTime, onSeek }: { events: DetectionEvent[]; currentTime: number; onSeek: (t: number) => void }) {
  const frames = useMemo(() => groupFrames(events), [events])
  const activeUrl = useMemo(() => {
    let best: Frame | undefined
    for (const f of frames) if (f.timestamp_s <= currentTime + 0.05) best = f
    return best && currentTime - best.timestamp_s < 2.5 ? best.url : null
  }, [frames, currentTime])

  return (
    <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 xl:grid-cols-4">
      {frames.map((f) => (
        <FrameThumb key={f.url} frame={f} active={f.url === activeUrl} onSelect={() => onSeek(f.timestamp_s)} />
      ))}
    </div>
  )
}
