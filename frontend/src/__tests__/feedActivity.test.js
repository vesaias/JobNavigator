// feedActivity.js — the Feed's read of what a job's in-flight runs mean.
//
// The invariant the whole file exists to protect: **a report that exists is
// never hidden by a run**. JobFeed derives `dScored` from the reports alone, so
// the only thing these helpers may do while a scored job is scored again is add
// a trailing item to the band and a spinner to the tabs. The second invariant is
// graceful degradation: `meta` is null for runs started before the backend
// carried it, and every function must fall back to a wordless form rather than
// invent a résumé name.
import { describe, it, expect } from 'vitest'
import {
  ANALYZE, TAILOR, TAILORED_KEY,
  activityText, feedActivity, flightDetail, flightTypes, ghostTabs, tabBusy, tabBusyHint, tailorMarkTitle,
} from '../screens/feedActivity'

const job = (over = {}) => ({ id: 'j1', company: 'Acme', ...over })
const analyzing = (names, depth = 'full') => job({
  in_flight: [ANALYZE],
  in_flight_detail: [{ job_type: ANALYZE, meta: { resume_names: names, depth } }],
})
const tailoring = (base, replaces = false) => job({
  in_flight: [TAILOR],
  in_flight_detail: [{ job_type: TAILOR, meta: { base_name: base, replaces } }],
})

// ── feedActivity ────────────────────────────────────────────────────────────
describe('feedActivity', () => {
  it('reads nothing off a job with no runs (and off no job at all)', () => {
    for (const j of [null, undefined, job(), job({ in_flight: [], in_flight_detail: [] })]) {
      const a = feedActivity(j)
      expect(a.running).toBe(false)
      expect(a.tailoring).toBe(false)
      expect(a.active).toBe(false)
      expect(a.tone).toBe(null)
      expect(a.rescoreNames).toEqual([])
    }
  })
  it('names the résumés a scoring run covers', () => {
    const a = feedActivity(analyzing(['Backend base', 'Platform base']))
    expect(a.running).toBe(true)
    expect(a.rescoreNames).toEqual(['Backend base', 'Platform base'])
    expect(a.depth).toBe('full')
    expect(a.tone).toBe('accent')
  })
  it('names the base a tailor runs from, and whether it replaces a copy', () => {
    const a = feedActivity(tailoring('Backend base', true))
    expect(a.tailoring).toBe(true)
    expect(a.baseName).toBe('Backend base')
    expect(a.replaces).toBe(true)
    expect(a.tone).toBe('ai')
  })
  it('gives scoring the ink when both run', () => {
    const a = feedActivity(job({
      in_flight: [ANALYZE, TAILOR],
      in_flight_detail: [
        { job_type: ANALYZE, meta: { resume_names: ['A'], depth: 'light' } },
        { job_type: TAILOR, meta: { base_name: 'A', replaces: false } },
      ],
    }))
    expect(a.running && a.tailoring).toBe(true)
    expect(a.tone).toBe('accent')
  })
  // an older backend answers in_flight only; a run must still count as running
  it('counts a run present in either field', () => {
    expect(feedActivity(job({ in_flight: [ANALYZE] })).running).toBe(true)
    expect(feedActivity(job({ in_flight_detail: [{ job_type: TAILOR, meta: null }] })).tailoring).toBe(true)
  })
  it('falls back to the job for `replaces` when meta is null', () => {
    expect(feedActivity(job({ in_flight: [TAILOR], tailored_resume_id: 7 })).replaces).toBe(true)
    expect(feedActivity(job({ in_flight: [TAILOR] })).replaces).toBe(false)
  })
  it('never returns a non-string or empty résumé name', () => {
    const a = feedActivity(job({
      in_flight: [ANALYZE],
      in_flight_detail: [{ job_type: ANALYZE, meta: { resume_names: ['Ok', '', null, 3, undefined] } }],
    }))
    expect(a.rescoreNames).toEqual(['Ok'])
  })
})

// ── activityText ────────────────────────────────────────────────────────────
describe('activityText', () => {
  it('counts the résumés, singular and plural', () => {
    expect(activityText(feedActivity(analyzing(['A'])))).toBe('Scoring 1 résumé')
    expect(activityText(feedActivity(analyzing(['A', 'B'])))).toBe('Scoring 2 résumés')
  })
  it('says Tailoring for a first copy and Re-tailoring for a replacement', () => {
    expect(activityText(feedActivity(tailoring('Backend base')))).toBe('Tailoring from Backend base')
    expect(activityText(feedActivity(tailoring('Backend base', true)))).toBe('Re-tailoring from Backend base')
  })
  it('joins both runs into one line', () => {
    const a = feedActivity(job({
      in_flight: [ANALYZE, TAILOR],
      in_flight_detail: [
        { job_type: ANALYZE, meta: { resume_names: ['A', 'B'] } },
        { job_type: TAILOR, meta: { base_name: 'A', replaces: false } },
      ],
    }))
    expect(activityText(a)).toBe('Scoring 2 résumés · Tailoring from A')
  })
  it('degrades to the wordless form when meta is missing', () => {
    expect(activityText(feedActivity(job({ in_flight: [ANALYZE] })))).toBe('Scoring…')
    expect(activityText(feedActivity(job({ in_flight: [TAILOR] })))).toBe('Tailoring…')
    expect(activityText(feedActivity(job({ in_flight: [TAILOR], tailored_resume_id: 4 })))).toBe('Re-tailoring…')
  })
  it('is empty when nothing runs', () => {
    expect(activityText(feedActivity(job()))).toBe('')
  })
})

// ── the card's ✦ mark ───────────────────────────────────────────────────────
describe('tailorMarkTitle', () => {
  it('separates a first copy from a replacement', () => {
    expect(tailorMarkTitle(feedActivity(tailoring('Base')))).toBe('Tailoring a résumé for this job…')
    expect(tailorMarkTitle(feedActivity(tailoring('Base', true)))).toContain('Re-tailoring from Base')
    expect(tailorMarkTitle(feedActivity(tailoring('Base', true)))).toContain('replaces')
  })
  it('still explains itself without a base name', () => {
    expect(tailorMarkTitle(feedActivity(job({ in_flight: [TAILOR], tailored_resume_id: 1 })))).toBe('Re-tailoring · replaces the current tailored résumé')
  })
})

// ── tabs ────────────────────────────────────────────────────────────────────
const tab = (name, tailored = false) => ({ name, tailored })
describe('tabBusy', () => {
  it('marks only the tabs whose résumé is in the scoring run', () => {
    const a = feedActivity(analyzing(['Backend base']))
    expect(tabBusy(a, tab('Backend base'))).toBe('accent')
    expect(tabBusy(a, tab('Platform base'))).toBe(null)
  })
  it('marks the tailored tab in --ai while a tailor runs', () => {
    const a = feedActivity(tailoring('Backend base', true))
    expect(tabBusy(a, tab(TAILORED_KEY, true))).toBe('ai')
    expect(tabBusy(a, tab('Backend base'))).toBe(null)
  })
  it('marks nothing when the run carries no names', () => {
    const a = feedActivity(job({ in_flight: [ANALYZE] }))
    expect(tabBusy(a, tab('Backend base'))).toBe(null)
  })
  it('hints the reason in the tab title', () => {
    expect(tabBusyHint('accent')).toBe(' · scoring again')
    expect(tabBusyHint('ai')).toBe(' · re-tailoring')
    expect(tabBusyHint(null)).toBe('')
  })
})

describe('ghostTabs', () => {
  const reports = [tab('Backend base'), tab(TAILORED_KEY, true)]
  it('ghosts only the résumés with no tab yet', () => {
    const a = feedActivity(analyzing(['Backend base', 'Platform base']))
    expect(ghostTabs(a, reports, 'Acme')).toEqual([{ key: 'Platform base', label: 'Platform base', tailored: false }])
  })
  it('ghosts the tailored copy as "{base} → {company}" when there is no tailored tab', () => {
    const a = feedActivity(tailoring('Backend base'))
    const g = ghostTabs(a, [tab('Backend base')], 'Acme')
    expect(g).toHaveLength(1)
    expect(g[0].tailored).toBe(true)
    expect(g[0].label).toBe('Backend base → Acme')
  })
  // override 2: the SCORE key stays "Tailored"; "{base} → {company}" is only a label
  it('does not ghost a tailored copy that already has its tab', () => {
    const a = feedActivity(tailoring('Backend base', true))
    expect(ghostTabs(a, reports, 'Acme')).toEqual([])
  })
  it('ghosts nothing when meta is missing', () => {
    expect(ghostTabs(feedActivity(job({ in_flight: [ANALYZE] })), reports, 'Acme')).toEqual([])
    expect(ghostTabs(feedActivity(job({ in_flight: [TAILOR] })), [], 'Acme')).toEqual([])
  })
  it('names the job when the company is unknown', () => {
    const g = ghostTabs(feedActivity(tailoring('Base')), [], '')
    expect(g[0].label).toBe('Base → this job')
  })
})

// ── the poll's two shapes ───────────────────────────────────────────────────
describe('flightTypes / flightDetail', () => {
  it('reads the plain shape an older backend answers', () => {
    expect(flightTypes([ANALYZE, TAILOR])).toEqual([ANALYZE, TAILOR])
    expect(flightDetail([ANALYZE])).toEqual([{ job_type: ANALYZE, meta: null }])
  })
  it('reads the detail shape', () => {
    const rows = [{ job_type: ANALYZE, meta: { resume_names: ['A'] } }]
    expect(flightTypes(rows)).toEqual([ANALYZE])
    expect(flightDetail(rows)).toEqual([{ job_type: ANALYZE, meta: { resume_names: ['A'] } }])
  })
  it('drops junk instead of writing a half job', () => {
    expect(flightTypes([null, {}, '', ANALYZE])).toEqual([ANALYZE])
    expect(flightDetail([null, {}, ANALYZE])).toEqual([{ job_type: ANALYZE, meta: null }])
    expect(flightTypes(undefined)).toEqual([])
    expect(flightDetail(undefined)).toEqual([])
  })
  // the round trip a poll tick makes: answer -> job fields -> feedActivity
  it('round-trips through feedActivity', () => {
    const rows = [{ job_type: TAILOR, meta: { base_name: 'Base', replaces: true } }]
    const a = feedActivity({ in_flight: flightTypes(rows), in_flight_detail: flightDetail(rows) })
    expect(a.tailoring).toBe(true)
    expect(activityText(a)).toBe('Re-tailoring from Base')
  })
})
