import { useEffect, useState } from 'react'
import { api, ApiError, type JobSummary } from '../api'

/** Recent jobs; refreshes every 3 s while any job is still running. */
export function useJobs(): { jobs: JobSummary[] | null; error: ApiError | null } {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined

    async function load() {
      try {
        const list = await api.listJobs(ctrl.signal)
        setJobs(list)
        setError(null)
        if (list.some((j) => j.status !== 'done' && j.status !== 'failed')) timer = setTimeout(load, 3000)
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setError(e instanceof ApiError ? e : new ApiError(0, String(e)))
        timer = setTimeout(load, 5000) // backend may still be starting
      }
    }

    load()
    return () => {
      ctrl.abort()
      clearTimeout(timer)
    }
  }, [])

  return { jobs, error }
}
