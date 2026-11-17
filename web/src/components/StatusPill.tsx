import type { JobState } from '../api'

const LABEL: Record<JobState, string> = {
  queued: 'Queued',
  ingesting: 'Processing',
  keyframes: 'Processing',
  detecting: 'Processing',
  reporting: 'Processing',
  done: 'Complete',
  failed: 'Failed',
}

/** Job status with a coloured dot; the word always accompanies the colour. */
export function StatusPill({ status }: { status: JobState }) {
  const running = !['queued', 'done', 'failed'].includes(status)
  const dot =
    status === 'done' ? 'bg-good' : status === 'failed' ? 'bg-critical' : running ? 'bg-ink animate-pulse' : 'bg-ink-3'
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-line px-2.5 font-mono text-[11.5px] text-ink-2">
      <span aria-hidden className={`size-1.5 rounded-full ${dot}`} />
      {LABEL[status]}
    </span>
  )
}
