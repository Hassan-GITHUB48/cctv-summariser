import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, uploadVideo, type Sampling } from '../api'
import { Button, EmptyState, ErrorPanel, Panel, Skeleton } from '../components/States'
import { StatusPill } from '../components/StatusPill'
import { useJobs } from '../hooks/useJobs'
import { formatBytes, relativeTime } from '../lib/format'

const ACCEPT = '.mp4,.mov,.avi,.mkv,.webm'
const SAMPLING: { value: Sampling; label: string; hint: string }[] = [
  { value: 'hybrid', label: 'Hybrid', hint: 'Scene cuts plus a frame at least every 2 s. Best for fixed cameras.' },
  { value: 'scene', label: 'Scene', hint: 'One frame per detected scene. Fastest, but misses activity on static shots.' },
  { value: 'interval', label: 'Interval', hint: 'One frame every 2 s regardless of content.' },
]

function UploadCard() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<() => void>(() => {})
  const [file, setFile] = useState<File | null>(null)
  const [sampling, setSampling] = useState<Sampling>('hybrid')
  const [startTime, setStartTime] = useState('')
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const uploading = progress !== null

  function pick(f: File | undefined) {
    if (!f) return
    setError(null)
    setFile(f)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (!uploading) pick(e.dataTransfer.files[0])
  }

  async function submit() {
    if (!file) return
    setError(null)
    setProgress(0)
    const { promise, abort } = uploadVideo(file, { sampling, startTime: startTime || undefined }, setProgress)
    abortRef.current = abort
    try {
      navigate(`/jobs/${await promise}`)
    } catch (e) {
      setProgress(null)
      setError(e instanceof ApiError ? e.message : String(e))
    }
  }

  return (
    <Panel title="New analysis">
      <div className="space-y-5 p-4">
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex min-h-44 flex-col items-center justify-center gap-2 rounded-md border border-dashed px-6 py-8 text-center transition-colors ${dragging ? 'border-ink bg-panel-2' : 'border-line-strong'}`}
        >
          {file ? (
            <>
              <p className="font-medium text-ink">{file.name}</p>
              <p className="font-mono text-[12px] text-ink-3">{formatBytes(file.size)}</p>
              {!uploading && (
                <Button variant="ghost" onClick={() => inputRef.current?.click()}>
                  Choose a different file
                </Button>
              )}
            </>
          ) : (
            <>
              <svg aria-hidden viewBox="0 0 24 24" className="size-7 text-ink-3" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M15 10l4.55-2.28A1 1 0 0121 8.62v6.76a1 1 0 01-1.45.9L15 14M4 18h9a2 2 0 002-2V8a2 2 0 00-2-2H4a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <p className="text-ink">Drop a CCTV clip here</p>
              <p className="text-[12.5px] text-ink-3">MP4, MOV, AVI, MKV or WebM · up to 500 MB</p>
              <Button variant="secondary" className="mt-2" onClick={() => inputRef.current?.click()}>
                Browse files
              </Button>
            </>
          )}
          <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        </div>

        <fieldset disabled={uploading} className="grid gap-5 sm:grid-cols-2">
          <div>
            <legend className="eyebrow mb-2">Frame sampling</legend>
            <div role="radiogroup" className="inline-flex rounded-md border border-line p-0.5">
              {SAMPLING.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  role="radio"
                  aria-checked={sampling === s.value}
                  onClick={() => setSampling(s.value)}
                  className={`h-7 rounded px-3 text-[13px] transition-colors ${sampling === s.value ? 'bg-panel-2 text-ink' : 'text-ink-3 hover:text-ink-2'}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[12.5px] text-ink-3">{SAMPLING.find((s) => s.value === sampling)!.hint}</p>
          </div>
          <div>
            <label htmlFor="start-time" className="eyebrow mb-2 block">
              Recording start <span className="normal-case tracking-normal">(optional)</span>
            </label>
            <input
              id="start-time"
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="h-8 w-full rounded-md border border-line bg-bg px-2 font-mono text-[12.5px] text-ink [color-scheme:dark] focus:border-ink-3 focus:outline-none"
            />
            <p className="mt-2 text-[12.5px] text-ink-3">Enables wall-clock times and after-hours flags.</p>
          </div>
        </fieldset>

        {error && <ErrorPanel title="Upload failed" message={error} />}

        {uploading ? (
          <div className="space-y-2">
            <div className="flex justify-between font-mono text-[12px] text-ink-2">
              <span>{progress! < 1 ? 'Uploading…' : 'Checking video…'}</span>
              <span>{Math.round(progress! * 100)}%</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-panel-2">
              <div className="h-full bg-ink transition-[width]" style={{ width: `${progress! * 100}%` }} />
            </div>
            <Button variant="ghost" onClick={() => abortRef.current()}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button onClick={submit} disabled={!file}>
            Analyse footage
          </Button>
        )}
      </div>
    </Panel>
  )
}

function RecentJobs() {
  const { jobs, error } = useJobs()

  let body
  if (error && !jobs) {
    body = (
      <div className="p-4">
        <ErrorPanel title="Can't load recent analyses" message={error.message} />
      </div>
    )
  } else if (!jobs) {
    body = (
      <ul className="divide-y divide-line">
        {[0, 1, 2].map((i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-3">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </li>
        ))}
      </ul>
    )
  } else if (jobs.length === 0) {
    body = <EmptyState title="No analyses yet" body="Upload a clip to get a timeline of detections and an incident report." />
  } else {
    body = (
      <ul className="max-h-[calc(100vh-11rem)] divide-y divide-line overflow-y-auto">
        {jobs.map((j) => (
          <li key={j.job_id}>
            <Link to={`/jobs/${j.job_id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-panel-2 focus-visible:bg-panel-2 focus-visible:outline-none">
              <div className="min-w-0 flex-1">
                <p className="truncate text-ink">{j.source}</p>
                <p className="font-mono text-[11.5px] text-ink-3">
                  {relativeTime(j.created_at)}
                  {j.status === 'done' && ` · ${j.incident_count} incident${j.incident_count === 1 ? '' : 's'}`}
                </p>
              </div>
              <StatusPill status={j.status} />
            </Link>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <Panel title="Recent analyses" className="lg:sticky lg:top-6 lg:self-start">
      {body}
    </Panel>
  )
}

export function UploadPage() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Review footage in minutes, not hours</h1>
          <p className="mt-1 max-w-2xl text-ink-2">
            Upload a clip: it's normalised with FFmpeg, sampled into keyframes, scanned for people and vehicles with YOLOv8, and
            summarised into a timestamped incident report.
          </p>
        </div>
        <UploadCard />
      </div>
      <RecentJobs />
    </div>
  )
}
