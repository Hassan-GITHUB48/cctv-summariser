import { useCallback, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type DetectionEvent, type JobStatus, type Report } from '../api'
import { FrameGallery } from '../components/FrameGallery'
import { IncidentCard } from '../components/IncidentCard'
import { StageProgress } from '../components/StageProgress'
import { Button, EmptyState, ErrorPanel, Panel, Skeleton, Spinner } from '../components/States'
import { StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import { useJob } from '../hooks/useJob'
import { downloadText, reportToMarkdown } from '../lib/markdown'

const STAGE_TITLE: Record<string, string> = {
  ingesting: 'normalising the video',
  keyframes: 'extracting keyframes',
  detecting: 'running detection',
  reporting: 'writing the report',
}

function BackLink() {
  return (
    <Link to="/" className="eyebrow inline-flex items-center gap-1 hover:text-ink-2">
      ← All analyses
    </Link>
  )
}

function JobHeader({ job, onExport }: { job: JobStatus; onExport?: () => void }) {
  const meta = job.meta
  const chips = meta
    ? [`${meta.duration_s.toFixed(1)}s`, `${meta.width}×${meta.height}`, `${meta.fps} fps`, job.sampling?.mode]
    : []
  const total = job.timings ? Object.values(job.timings).reduce((a, b) => a + b, 0) : null
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <BackLink />
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="truncate text-xl font-semibold tracking-tight">{job.source}</h1>
          <StatusPill status={job.status} />
        </div>
        <p className="mt-1 font-mono text-[11.5px] text-ink-3">
          {[`job ${job.job_id}`, ...chips.filter(Boolean), total !== null && `processed in ${total.toFixed(1)}s`].filter(Boolean).join(' · ')}
        </p>
      </div>
      {onExport && (
        <Button variant="secondary" onClick={onExport}>
          Export report (.md)
        </Button>
      )}
    </div>
  )
}

function ProcessingView({ job }: { job: JobStatus }) {
  const label = job.status === 'queued' ? 'Waiting for a free worker' : `Processing: ${STAGE_TITLE[job.status] ?? job.status}`
  return (
    <Panel title="Pipeline">
      <div className="p-5">
        <div className="mb-5 flex items-center gap-3">
          <Spinner />
          <p className="text-ink">{label}…</p>
        </div>
        <StageProgress job={job} />
        <p className="mt-5 text-[12.5px] text-ink-3">This page updates automatically. Most clips finish in under a minute.</p>
      </div>
    </Panel>
  )
}

function ResultsView({ job, events, report }: { job: JobStatus; events: DetectionEvent[]; report: Report | null }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [videoError, setVideoError] = useState(false)
  const duration = job.meta?.duration_s ?? 0
  const incidents = useMemo(() => [...(report?.incidents ?? [])].sort((a, b) => a.start_s - b.start_s), [report])

  const seek = useCallback((t: number) => {
    const v = videoRef.current
    setCurrentTime(t)
    if (!v) return
    v.currentTime = t
    const rect = v.getBoundingClientRect()
    if (rect.top < 0 || rect.bottom > window.innerHeight) v.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [])

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="min-w-0 space-y-6">
        <div className="overflow-hidden rounded-lg border border-line bg-black">
          {videoError ? (
            <div className="grid aspect-video place-items-center">
              <EmptyState title="Video unavailable" body="The normalised video could not be loaded. Detections and the report are still available." />
            </div>
          ) : (
            <video
              ref={videoRef}
              src={api.videoUrl(job.job_id)}
              controls
              preload="metadata"
              className="block aspect-video max-h-[44vh] w-full"
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onSeeked={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onError={() => setVideoError(true)}
            />
          )}
        </div>

        <Panel title="Timeline" aside={<span className="font-mono text-[11.5px] text-ink-3">{events.length} detections</span>}>
          {events.length === 0 && incidents.length === 0 ? (
            <EmptyState title="Nothing detected" body="No people or vehicles were found in the sampled frames." />
          ) : (
            <Timeline duration={duration} events={events} incidents={incidents} currentTime={currentTime} onSeek={seek} />
          )}
        </Panel>

        <Panel title="Keyframes with detections">
          {events.length === 0 ? (
            <EmptyState title="No keyframes to show" body="Frames appear here when the detector finds a person or vehicle." />
          ) : (
            <FrameGallery events={events} currentTime={currentTime} onSeek={seek} />
          )}
        </Panel>
      </div>

      <aside className="min-w-0 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
        <Panel title="Incident report" aside={report && <span className="font-mono text-[11px] text-ink-3">{report.model}</span>}>
          {report ? (
            <div className="space-y-4 p-4">
              <p className="leading-relaxed text-ink-2">{report.summary}</p>
              {incidents.length === 0 ? (
                <EmptyState title="No incidents" body="The footage contains nothing that needs attention." />
              ) : (
                <div className="space-y-3">
                  {incidents.map((inc, i) => (
                    <IncidentCard
                      key={i}
                      incident={inc}
                      active={currentTime >= inc.start_s - 0.5 && currentTime <= inc.end_s + 0.5}
                      onSeek={seek}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : (
            <EmptyState title="No report" body="This job was processed without the LLM report stage." />
          )}
        </Panel>
      </aside>
    </div>
  )
}

function LoadingView({ withHeader = true }: { withHeader?: boolean }) {
  return (
    <div className="space-y-6" aria-busy>
      {withHeader && (
        <div className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-6 w-72" />
          <Skeleton className="h-3 w-96" />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <Skeleton className="aspect-video w-full rounded-lg" />
          <Skeleton className="h-36 w-full rounded-lg" />
        </div>
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    </div>
  )
}

export function JobPage() {
  const { id = '' } = useParams()
  const { job, events, report, error, retry } = useJob(id)

  if (error?.status === 404 || error?.status === 422) {
    return (
      <div className="space-y-4">
        <BackLink />
        <Panel title="Not found">
          <EmptyState
            title="This analysis doesn't exist"
            body={<>No job with ID <span className="font-mono">{id}</span>. It may have been deleted.</>}
            action={<Link to="/" className="text-ink underline underline-offset-4">Start a new analysis</Link>}
          />
        </Panel>
      </div>
    )
  }
  if (error && !job) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorPanel title="Couldn't load this analysis" message={error.message} onRetry={retry} />
      </div>
    )
  }
  if (!job) return <LoadingView />

  const done = job.status === 'done'
  const ready = done && events !== null
  const onExport = ready && report
    ? () => downloadText(`incident-report-${job.job_id}.md`, reportToMarkdown(job, report, events))
    : undefined

  return (
    <div className="space-y-6">
      <JobHeader job={job} onExport={onExport} />
      {error && <ErrorPanel title="Lost connection to the API" message={error.message} onRetry={retry} />}
      {job.status === 'failed' ? (
        <div className="space-y-6">
          <ErrorPanel
            title={`Processing failed${job.failed_stage ? ` while ${STAGE_TITLE[job.failed_stage]}` : ''}`}
            message={job.error ?? 'Unknown error'}
          >
            <Link to="/" className="inline-flex h-8 items-center rounded-md border border-line-strong px-3 text-[13px] hover:bg-panel-2">
              Upload another clip
            </Link>
          </ErrorPanel>
          <Panel title="Pipeline">
            <div className="p-5">
              <StageProgress job={job} />
            </div>
          </Panel>
        </div>
      ) : !done ? (
        <ProcessingView job={job} />
      ) : ready ? (
        <ResultsView job={job} events={events} report={report} />
      ) : (
        <LoadingView withHeader={false} />
      )}
    </div>
  )
}
