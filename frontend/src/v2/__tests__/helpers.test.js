// The pure helpers the v2 screens and primitives export. Components are out of
// scope here — this file covers the functions and constant tables that carry
// logic (score banding, section counts, prototype-pollution guards, the two
// Cover Letter lookup tables) and nothing that needs a DOM tree.
//
// ui.jsx / ResumeSections.jsx / CoverLetters.jsx all pull React (and, through
// ui.jsx, theme.css) on import; jsdom + vitest's css:false handle that, so the
// helpers can be imported from their real modules rather than copied.
import { describe, it, expect, vi } from 'vitest'
import { scoreTone, kb as uiKb } from '../ui'
import {
  DANGEROUS, EMPTY, SECTION_ORDER, sectionCounts, makeMutators, kb as sectionKb,
} from '../ResumeSections'
import { LENGTHS, STAGE_CLASS } from '../CoverLetters'

// ── ui.jsx: scoreTone ───────────────────────────────────────────────────────
describe('scoreTone', () => {
  it('is neutral only for a missing score', () => {
    expect(scoreTone(null)).toBe('neutral')
    expect(scoreTone(undefined)).toBe('neutral')
  })
  it('bands at 70 (good) and 50 (warn), inclusive on the boundary', () => {
    expect(scoreTone(100)).toBe('good')
    expect(scoreTone(70)).toBe('good')
    expect(scoreTone(69.9)).toBe('warn')
    expect(scoreTone(50)).toBe('warn')
    expect(scoreTone(49.9)).toBe('bad')
    expect(scoreTone(0)).toBe('bad')
  })
  it('treats 0 as a real score, not as "no score"', () => {
    // `s == null` and not `!s`, so a genuine zero still reads red rather than grey
    expect(scoreTone(0)).not.toBe('neutral')
  })
  it('never returns anything outside the ring tone set', () => {
    const tones = new Set(['neutral', 'good', 'warn', 'bad'])
    for (const s of [null, undefined, -10, 0, 1, 49, 50, 69, 70, 99, 100, 1000]) {
      expect(tones.has(scoreTone(s)), String(s)).toBe(true)
    }
  })
})

// ── kb(): the keyboard shim on span/div controls ────────────────────────────
describe('kb', () => {
  const ev = (key) => ({ key, preventDefault: vi.fn() })

  for (const [name, kb] of [['ui.jsx', uiKb], ['ResumeSections.jsx', sectionKb]]) {
    describe(name, () => {
      it('makes the element a tab stop with a role', () => {
        expect(kb(() => {})).toMatchObject({ tabIndex: 0, role: 'button' })
        expect(kb(() => {}, 'menuitem').role).toBe('menuitem')
      })
      it('fires on Enter and Space, swallowing the default scroll', () => {
        for (const key of ['Enter', ' ']) {
          const fn = vi.fn(); const e = ev(key)
          kb(fn).onKeyDown(e)
          expect(fn, key).toHaveBeenCalledTimes(1)
          expect(fn, key).toHaveBeenCalledWith(e)
          expect(e.preventDefault, key).toHaveBeenCalledTimes(1)
        }
      })
      it('ignores every other key and leaves the default alone', () => {
        for (const key of ['a', 'Escape', 'Tab', 'Spacebar', 'ArrowDown']) {
          const fn = vi.fn(); const e = ev(key)
          kb(fn).onKeyDown(e)
          expect(fn, key).not.toHaveBeenCalled()
          expect(e.preventDefault, key).not.toHaveBeenCalled()
        }
      })
    })
  }

  it('the two copies are the same contract (ui.jsx stays a leaf of the import graph)', () => {
    const a = uiKb(() => {}, 'menuitem'); const b = sectionKb(() => {}, 'menuitem')
    expect(Object.keys(a).sort()).toEqual(Object.keys(b).sort())
    expect([a.tabIndex, a.role]).toEqual([b.tabIndex, b.role])
  })
})

// ── ResumeSections.jsx ──────────────────────────────────────────────────────
describe('DANGEROUS', () => {
  it('names the three prototype-pollution keys', () => {
    expect([...DANGEROUS].sort()).toEqual(['__proto__', 'constructor', 'prototype'])
  })
})

describe('EMPTY / SECTION_ORDER', () => {
  it('SECTION_ORDER lists the seven sections, Header first', () => {
    expect(SECTION_ORDER).toEqual(['Header', 'Summary', 'Experience', 'Skills', 'Education', 'Projects', 'Publications'])
  })
  it('EMPTY carries a slot for every section the order names', () => {
    for (const name of SECTION_ORDER) expect(EMPTY, name).toHaveProperty(name.toLowerCase())
  })
  it('EMPTY is the zero state sectionCounts reads as all zeroes', () => {
    expect(sectionCounts(EMPTY)).toEqual({ Experience: 0, Skills: 0, Education: 0, Projects: 0, Publications: 0 })
  })
})

describe('sectionCounts', () => {
  it('counts list sections by length and Skills by group', () => {
    expect(sectionCounts({
      experience: [1, 2, 3],
      skills: { Languages: ['py'], Cloud: [] },
      education: [1],
      projects: [1, 2],
      publications: [],
    })).toEqual({ Experience: 3, Skills: 2, Education: 1, Projects: 2, Publications: 0 })
  })
  it('reads real data, which is looser than EMPTY: missing sections count zero', () => {
    expect(sectionCounts({})).toEqual({ Experience: 0, Skills: 0, Education: 0, Projects: 0, Publications: 0 })
    expect(sectionCounts({ experience: null, skills: null })).toMatchObject({ Experience: 0, Skills: 0 })
  })
  it('never reports Header or Summary — they have no count', () => {
    expect(Object.keys(sectionCounts(EMPTY))).toEqual(['Experience', 'Skills', 'Education', 'Projects', 'Publications'])
  })
})

describe('makeMutators', () => {
  it('mutate() deep-clones, so the caller\'s object is never written through', () => {
    const data = { summary: 'old', experience: [{ title: 'A' }] }
    const onData = vi.fn()
    makeMutators(data, onData).mutate((d) => { d.summary = 'new'; d.experience[0].title = 'B' })
    expect(onData).toHaveBeenCalledTimes(1)
    expect(onData.mock.calls[0][0]).toEqual({ summary: 'new', experience: [{ title: 'B' }] })
    expect(data).toEqual({ summary: 'old', experience: [{ title: 'A' }] })
  })
  it('mutate() keeps unknown keys real data carries', () => {
    const onData = vi.fn()
    makeMutators({ summary: 's', _tailor_context: 'kept', weird: { x: 1 } }, onData).mutate((d) => { d.summary = 't' })
    expect(onData.mock.calls[0][0]).toEqual({ summary: 't', _tailor_context: 'kept', weird: { x: 1 } })
  })
  it('mutate() falls back to EMPTY for null data', () => {
    const onData = vi.fn()
    makeMutators(null, onData).mutate((d) => { d.summary = 'x' })
    expect(onData.mock.calls[0][0]).toEqual({ ...EMPTY, summary: 'x' })
  })
  it('setField() writes one dotted path', () => {
    const onData = vi.fn()
    makeMutators({ header: { name: '', contact_items: [] } }, onData).setField('header.name', 'Ada')
    expect(onData.mock.calls[0][0]).toEqual({ header: { name: 'Ada', contact_items: [] } })
  })
  it('setField() writes through an array index', () => {
    const onData = vi.fn()
    makeMutators({ experience: [{ title: 'A' }, { title: 'B' }] }, onData).setField('experience.1.title', 'C')
    expect(onData.mock.calls[0][0].experience).toEqual([{ title: 'A' }, { title: 'C' }])
  })
  it('setField() refuses a path containing a DANGEROUS key, and calls nothing', () => {
    for (const path of ['__proto__.polluted', 'constructor.prototype.x', 'a.prototype.b', 'header.__proto__']) {
      const onData = vi.fn()
      makeMutators({ header: {} }, onData).setField(path, 'boom')
      expect(onData, path).not.toHaveBeenCalled()
    }
    expect({}.polluted).toBeUndefined()
  })
  it('setField() bails out mid-path rather than creating objects', () => {
    const onData = vi.fn()
    makeMutators({ header: { name: '' } }, onData).setField('nope.deeper.name', 'x')
    // the walk hits undefined and gives up; mutate() still persists, unchanged —
    // no `nope` branch is invented on the way down
    expect(onData).toHaveBeenCalledTimes(1)
    expect(onData.mock.calls[0][0]).toEqual({ header: { name: '' } })
  })
  it('setField() leaves the document alone when the leaf holder is not an object', () => {
    const onData = vi.fn()
    makeMutators({ summary: 'text' }, onData).setField('summary.length', 9)
    expect(onData.mock.calls[0][0]).toEqual({ summary: 'text' })
  })
  it('setField() coerces a non-string path', () => {
    const onData = vi.fn()
    makeMutators({ 5: 'five' }, onData).setField(5, 'six')
    expect(onData.mock.calls[0][0]).toEqual({ 5: 'six' })
  })
})

// ── CoverLetters.jsx ────────────────────────────────────────────────────────
describe('LENGTHS', () => {
  it('is the three [value, label] pairs the length picker offers', () => {
    expect(LENGTHS).toEqual([['concise', 'Concise'], ['standard', 'Standard'], ['detailed', 'Detailed']])
  })
  it('has a Segmented-shaped payload: unique values, label = capitalised value', () => {
    expect(new Set(LENGTHS.map(([v]) => v)).size).toBe(LENGTHS.length)
    for (const [v, label] of LENGTHS) expect(label).toBe(v[0].toUpperCase() + v.slice(1))
  })
})

describe('STAGE_CLASS', () => {
  it('maps every application stage a row can show to a colour class', () => {
    expect(STAGE_CLASS).toEqual({
      applied: 'cc-smartrecruiters',
      interview: 'cc-workday',
      offer: 'cc-tier1',
      rejected: 'cc-generic',
    })
  })
  it('gives each stage its own class, so two stages never read alike', () => {
    expect(new Set(Object.values(STAGE_CLASS)).size).toBe(Object.keys(STAGE_CLASS).length)
  })
  it('is a plain lookup: an unknown stage yields undefined, not a wrong colour', () => {
    expect(STAGE_CLASS.ghosted).toBeUndefined()
    expect(STAGE_CLASS.saved).toBeUndefined()
  })
})
