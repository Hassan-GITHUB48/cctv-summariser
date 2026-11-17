import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type DetectionEvent, type JobStatus, type Report } from '../api'

const POLL_MS = 1000
const TERMINAL = new Set(['done', 'failed'])

export interface JobData {
  job: JobStatus | null
  events: DetectionEvent[] | null
  report: Report | null
  error: ApiError | null
  retry: () => void
}

/**
 * Polls GET /jobs/{id} every second until the job is done or failed, then loads
 * events and the report once. A missing report (404) is not an error.
 */
export function useJob(id: string): JobData {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [events, setEvents] = useState<DetectionEvent[] | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined

    async function loadResults() {
      const [ev, rep] = await Promise.all([
        api.getEvents(id, ctrl.signal),
        api.getReport(id, ctrl.signal).catch((e) => (e instanceof ApiError && e.status === 404 ? null : Promise.reject(e))),
      ])
      setEvents(ev)
      setReport(rep)
    }

    async function poll() {
      try {
        const next = await api.getJob(id, ctrl.signal)
        setJob(next)
        setError(null)
        if (next.status === 'done') await loadResults()
        else if (!TERMINAL.has(next.status)) timer = setTimeout(poll, POLL_MS)
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setError(e instanceof ApiError ? e : new ApiError(0, String(e)))
      }
    }

    poll()
    return () => {
      ctrl.abort()
      clearTimeout(timer)
    }
  }, [id, attempt])

  const retry = useCallback(() => {
    setError(null)
    setAttempt((n) => n + 1)
  }, [])

  return { job, events, report, error, retry }
}
