import type { Incident } from '../api'
import { timeRange } from '../lib/format'
import { severityStyle } from '../lib/severity'

export function SeverityBadge({ severity }: { severity: number }) {
  const { label, color } = severityStyle(severity)
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11.5px] text-ink-2">
      <span aria-hidden className="inline-flex gap-[2px]">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className="h-2.5 w-1 rounded-[1px]" style={{ background: n <= severity ? color : 'var(--color-line-strong)' }} />
        ))}
      </span>
      S{severity} · {label}
    </span>
  )
}

/** One incident: severity bar on the left edge, clickable timecode that seeks the video. */
export function IncidentCard({ incident, active, onSeek }: { incident: Incident; active: boolean; onSeek: (t: number) => void }) {
  const { color } = severityStyle(incident.severity)
  return (
    <article className={`relative overflow-hidden rounded-md border bg-panel-2/60 py-3 pl-4 pr-3 ${active ? 'border-line-strong' : 'border-line'}`}>
      <span aria-hidden className="absolute inset-y-0 left-0 w-[3px]" style={{ background: color }} />
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onSeek(incident.start_s)}
          className="rounded font-mono text-[12px] text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink hover:decoration-ink focus-visible:outline-2 focus-visible:outline-ink"
          title="Jump to this moment"
        >
          {timeRange(incident.start_s, incident.end_s)}
        </button>
        <SeverityBadge severity={incident.severity} />
      </div>
      <h3 className="mt-1.5 font-medium leading-snug text-ink">{incident.title}</h3>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{incident.description}</p>
      <p className="mt-2 text-[13px] text-ink">
        <span className="eyebrow mr-1.5">Action</span>
        {incident.recommended_action}
      </p>
    </article>
  )
}
