import { describe, expect, it } from 'vitest'
import type { JobStatus, Report } from '../api'
import { orderedLabels } from './classes'
import { mmss, relativeTime, timeRange } from './format'
import { reportToMarkdown } from './markdown'
import { severityStyle } from './severity'
import { markersByLabel, ticks } from './timeline'

describe('format', () => {
  it('formats timecodes', () => {
    expect(mmss(0)).toBe('00:00')
    expect(mmss(75.9)).toBe('01:15')
    expect(timeRange(18, 18.4)).toBe('00:18')
    expect(timeRange(40.9, 48.9)).toBe('00:40–00:48')
  })
  it('formats relative time', () => {
    const now = new Date('2026-11-17T12:00:00Z')
    expect(relativeTime('2026-11-17T11:59:30Z', now)).toBe('just now')
    expect(relativeTime('2026-11-17T11:45:00Z', now)).toBe('15 min ago')
  })
})

describe('classes', () => {
  it('keeps canonical order regardless of input order', () => {
    expect(orderedLabels(['bicycle', 'person', 'dog', 'car'])).toEqual(['person', 'car', 'bicycle', 'dog'])
  })
})

describe('severity', () => {
  it('maps every level to a label', () => {
    expect([1, 2, 3, 4, 5].map((s) => severityStyle(s).label)).toEqual(['Low', 'Low', 'Medium', 'High', 'Critical'])
  })
})

describe('reportToMarkdown', () => {
  const job = { job_id: 'abc', source: 'clip.mp4', meta: { duration_s: 53.9, width: 768, height: 432, fps: 12 } } as JobStatus
  const report: Report = {
    job_id: 'abc', model: 'claude-sonnet-5-5', summary: 'Quiet night.', created_at: '2026-11-17T10:00:00Z',
    incidents: [
      { start_s: 40, end_s: 48, title: 'Late', description: 'B', severity: 3, recommended_action: 'Review', candidate_ids: ['C2'] },
      { start_s: 2, end_s: 6, title: 'Early', description: 'A', severity: 1, recommended_action: 'None', candidate_ids: ['C1'] },
    ],
  }
  it('renders incidents in time order with severity labels', () => {
    const md = reportToMarkdown(job, report, [{ label: 'person' }, { label: 'person' }] as never)
    expect(md).toContain('# Incident report: clip.mp4')
    expect(md).toContain('**Detections:** person 2')
    expect(md.indexOf('Early')).toBeLessThan(md.indexOf('Late'))
    expect(md).toContain('**Severity:** 3/5 (Medium)')
  })
})

describe('timeline', () => {
  it('picks a nice tick step', () => {
    expect(ticks(53.9)).toEqual([0, 10, 20, 30, 40, 50])
    expect(ticks(12)).toEqual([0, 2, 4, 6, 8, 10, 12])
    expect(ticks(0)).toEqual([0])
  })
  it('groups detections into one marker per label per frame', () => {
    const ev = (t: number, label: string, confidence: number) => ({ timestamp_s: t, label, confidence }) as never
    const lanes = markersByLabel([ev(2, 'person', 0.5), ev(2, 'person', 0.9), ev(4, 'person', 0.7), ev(2, 'car', 0.8)])
    expect(lanes.get('person')).toEqual([
      { label: 'person', timestamp_s: 2, count: 2, maxConfidence: 0.9 },
      { label: 'person', timestamp_s: 4, count: 1, maxConfidence: 0.7 },
    ])
    expect(lanes.get('car')?.length).toBe(1)
  })
})
