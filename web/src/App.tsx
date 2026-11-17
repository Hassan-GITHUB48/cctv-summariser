import { Link, Route, Routes } from 'react-router'
import { EmptyState, Panel } from './components/States'
import { JobPage } from './pages/JobPage'
import { UploadPage } from './pages/UploadPage'

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex h-12 max-w-[1440px] items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-ink">
            <svg aria-hidden viewBox="0 0 32 32" className="size-5">
              <circle cx="16" cy="16" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
              <circle cx="16" cy="16" r="3" fill="var(--color-critical)" />
            </svg>
            <span className="font-medium tracking-tight">CCTV Incident Summariser</span>
          </Link>
          <Link to="/" className="eyebrow hover:text-ink-2">
            New analysis
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/jobs/:id" element={<JobPage />} />
        <Route
          path="*"
          element={
            <Panel title="Not found">
              <EmptyState title="Page not found" action={<Link to="/" className="text-ink underline underline-offset-4">Go to dashboard</Link>} />
            </Panel>
          }
        />
      </Routes>
    </Shell>
  )
}
