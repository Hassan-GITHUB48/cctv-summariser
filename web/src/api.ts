// Typed client for the FastAPI backend. Types mirror api/schemas.py.

export const API_BASE = '/api'

export type JobState = 'queued' | 'ingesting' | 'keyframes' | 'detecting' | 'reporting' | 'done' | 'failed'
export type StageName = 'ingesting' | 'keyframes' | 'detecting' | 'reporting'
export type StageState = 'pending' | 'running' | 'done' | 'failed'
export type Sampling = 'hybrid' | 'scene' | 'interval'

export interface JobSummary {
  job_id: string
  source: string
  status: JobState
  incident_count: number
  created_at: string
  updated_at: string
}

export interface VideoMeta {
  duration_s: number
  fps: number
  width: number
  height: number
  codec: string
}

export interface JobStatus {
  job_id: string
  source: string
  status: JobState
  error: string | null
  failed_stage: StageName | null
  progress: number
  stages: { name: StageName; state: StageState }[]
  meta: VideoMeta | null
  sampling: { mode: Sampling; interval_s: number | null; max_gap_s: number | null } | null
  timings: Record<string, number> | null
  created_at: string
  updated_at: string
}

export interface DetectionEvent {
  timestamp_s: number
  frame_index: number
  label: string
  confidence: number
  bbox: [number, number, number, number]
  frame_url: string
}

export interface Incident {
  start_s: number
  end_s: number
  title: string
  description: string
  severity: number
  recommended_action: string
  candidate_ids: string[]
}

export interface Report {
  job_id: string
  model: string
  summary: string
  incidents: Incident[]
  created_at: string
}

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const UNREACHABLE = 'Cannot reach the API. Is the backend running on port 8000?'
// The dev proxy (or a load balancer) answers 502/503/504 itself when the backend is down.
const GATEWAY_ERRORS = new Set([502, 503, 504])

/** Turn a FastAPI error body ({detail: string | [{msg}]}) into a readable message. */
async function errorFrom(res: Response): Promise<ApiError> {
  let message = GATEWAY_ERRORS.has(res.status) ? UNREACHABLE : `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
  } catch {
    // non-JSON body (e.g. proxy error page): keep the status line
  }
  return new ApiError(res.status, message)
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { signal })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError(0, UNREACHABLE)
  }
  if (!res.ok) throw await errorFrom(res)
  return res.json() as Promise<T>
}

export const api = {
  listJobs: (signal?: AbortSignal) => getJson<JobSummary[]>('/jobs?limit=20', signal),
  getJob: (id: string, signal?: AbortSignal) => getJson<JobStatus>(`/jobs/${id}`, signal),
  getEvents: (id: string, signal?: AbortSignal) => getJson<DetectionEvent[]>(`/jobs/${id}/events`, signal),
  getReport: (id: string, signal?: AbortSignal) => getJson<Report>(`/jobs/${id}/report`, signal),
  videoUrl: (id: string) => `${API_BASE}/jobs/${id}/video`,
  frameUrl: (frameUrl: string) => `${API_BASE}${frameUrl}`,
}

/**
 * Upload with progress. fetch() can't report upload progress, so this uses XHR.
 * Resolves with the new job id; rejects with ApiError (413/415/422 carry a readable detail).
 */
export function uploadVideo(
  file: File,
  options: { sampling: Sampling; startTime?: string },
  onProgress: (fraction: number) => void,
): { promise: Promise<string>; abort: () => void } {
  const xhr = new XMLHttpRequest()
  const promise = new Promise<string>((resolve, reject) => {
    const form = new FormData()
    form.append('video', file)
    form.append('sampling', options.sampling)
    if (options.startTime) form.append('start_time', options.startTime)

    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    xhr.onload = () => {
      let body: { job_id?: string; detail?: unknown } = {}
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // ignore: handled by the status check below
      }
      if (xhr.status === 202 && body.job_id) return resolve(body.job_id)
      const fallback = GATEWAY_ERRORS.has(xhr.status) ? UNREACHABLE : `Upload failed (${xhr.status})`
      const detail = typeof body.detail === 'string' ? body.detail : fallback
      reject(new ApiError(xhr.status, detail))
    }
    xhr.onerror = () => reject(new ApiError(0, UNREACHABLE))
    xhr.onabort = () => reject(new ApiError(0, 'Upload cancelled'))
    xhr.open('POST', `${API_BASE}/jobs`)
    xhr.send(form)
  })
  return { promise, abort: () => xhr.abort() }
}
