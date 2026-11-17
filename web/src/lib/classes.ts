// Object classes in a fixed order. Colour follows the class, never its rank or count,
// so "person" is always the same blue whichever classes a clip contains.
export const CLASS_ORDER = ['person', 'car', 'truck', 'motorcycle', 'bicycle'] as const

const CLASS_COLOR: Record<string, string> = {
  person: 'var(--color-cls-person)',
  car: 'var(--color-cls-car)',
  truck: 'var(--color-cls-truck)',
  motorcycle: 'var(--color-cls-motorcycle)',
  bicycle: 'var(--color-cls-bicycle)',
}

export function classColor(label: string): string {
  return CLASS_COLOR[label] ?? 'var(--color-ink-3)'
}

/** Labels present in the data, in the canonical order (unknown labels last, alphabetically). */
export function orderedLabels(labels: Iterable<string>): string[] {
  const present = new Set(labels)
  const known = CLASS_ORDER.filter((c) => present.has(c))
  const unknown = [...present].filter((l) => !(CLASS_ORDER as readonly string[]).includes(l)).sort()
  return [...known, ...unknown]
}
