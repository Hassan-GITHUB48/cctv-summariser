// Severity 1-5 -> reserved status colours. Severity is always shown with its number and
// a word, so colour never carries the meaning alone.
export interface SeverityStyle {
  label: string
  color: string
}

export function severityStyle(severity: number): SeverityStyle {
  if (severity >= 5) return { label: 'Critical', color: 'var(--color-critical)' }
  if (severity === 4) return { label: 'High', color: 'var(--color-serious)' }
  if (severity === 3) return { label: 'Medium', color: 'var(--color-warning)' }
  return { label: 'Low', color: 'var(--color-ink-3)' }
}
