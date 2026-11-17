import type { JobStatus, StageName, StageState } from '../api'

const STAGE_LABEL: Record<StageName, { title: string; detail: string }> = {
  ingesting: { title: 'Normalise', detail: 'FFmpeg → 720p H.264' },
  keyframes: { title: 'Keyframes', detail: 'Scene cuts + 2 s max gap' },
  detecting: { title: 'Detect', detail: 'YOLOv8n people & vehicles' },
  reporting: { title: 'Report', detail: 'LLM incident summary' },
}

// Stage names (status values) -> keys used in the job's per-stage timings.
const TIMING_KEY: Record<StageName, string> = {
  ingesting: 'ingest',
  keyframes: 'keyframes',
  detecting: 'detect',
  reporting: 'report',
}

function StageIcon({ state }: { state: StageState }) {
  const base = 'grid size-6 shrink-0 place-items-center rounded-full border text-[11px] font-bold'
  if (state === 'done') return <span className={`${base} border-good bg-good text-bg`}>✓</span>
  if (state === 'failed') return <span className={`${base} border-critical bg-critical text-bg`}>!</span>
  if (state === 'running')
    return (
      <span className={`${base} border-ink`}>
        <span className="size-2 animate-ping rounded-full bg-ink" />
      </span>
    )
  return <span className={`${base} border-line-strong`} />
}

/** Four-step pipeline indicator with an overall progress bar. */
export function StageProgress({ job }: { job: JobStatus }) {
  return (
    <div>
      <div className="h-1 overflow-hidden rounded-full bg-panel-2" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(job.progress * 100)}>
        <div
          className={`h-full transition-[width] duration-500 ${job.status === 'failed' ? 'bg-critical' : 'bg-ink'}`}
          style={{ width: `${Math.max(job.progress * 100, job.status === 'queued' ? 0 : 4)}%` }}
        />
      </div>
      <ol className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {job.stages.map(({ name, state }) => (
          <li key={name} className="flex items-start gap-3">
            <StageIcon state={state} />
            <div className="min-w-0">
              <p className={`font-medium ${state === 'pending' ? 'text-ink-3' : 'text-ink'}`}>{STAGE_LABEL[name].title}</p>
              <p className="text-[12.5px] text-ink-3">
                {STAGE_LABEL[name].detail}
                {job.timings?.[TIMING_KEY[name]] !== undefined && (
                  <span className="ml-1.5 font-mono text-ink-2">{job.timings[TIMING_KEY[name]].toFixed(2)}s</span>
                )}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
