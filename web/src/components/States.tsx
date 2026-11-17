import type { ReactNode } from 'react'

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block size-4 animate-spin rounded-full border-2 border-line-strong border-t-ink ${className}`}
    />
  )
}

/** Placeholder block shown while content loads, sized like the content it replaces. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded bg-panel-2 ${className}`} />
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="mb-1 text-ink-3">{icon}</div>}
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="max-w-sm text-ink-2">{body}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function ErrorPanel({ title, message, onRetry, children }: {
  title: string
  message: string
  onRetry?: () => void
  children?: ReactNode
}) {
  return (
    <div role="alert" className="rounded-md border border-critical/40 bg-critical/[0.06] p-4">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-critical text-[11px] font-bold text-bg">!</span>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">{title}</p>
          <p className="mt-1 break-words font-mono text-[12.5px] text-ink-2">{message}</p>
          {(onRetry || children) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {onRetry && <Button variant="secondary" onClick={onRetry}>Retry</Button>}
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  const styles = {
    primary: 'bg-ink text-bg hover:bg-white disabled:bg-line-strong disabled:text-ink-3',
    secondary: 'border border-line-strong text-ink hover:bg-panel-2 disabled:text-ink-3',
    ghost: 'text-ink-2 hover:text-ink hover:bg-panel-2',
  }[variant]
  return (
    <button
      className={`inline-flex h-8 items-center gap-2 rounded-md px-3 text-[13px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cls-person disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    />
  )
}

/** Bordered section with an uppercase heading row. */
export function Panel({ title, aside, children, className = '' }: {
  title: string
  aside?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-lg border border-line bg-panel ${className}`}>
      <header className="flex h-10 items-center justify-between gap-3 border-b border-line px-4">
        <h2 className="eyebrow">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  )
}
