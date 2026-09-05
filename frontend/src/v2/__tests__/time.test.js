// time.js — the clock every v2 screen shares.
//
// The `describeCron, checked` table at the bottom of time.js used to be run by
// hand and pasted back ("There is no test runner for the frontend"). It is now a
// real assertion table: rows 1-20 below are that comment block, verbatim, with
// the same pinned FROM. If a row here ever disagrees with the comment, the
// comment is the thing that drifted.
//
// TZ: `whenShort` uses LOCAL getters on purpose (a UTC instant read in the
// viewer's zone), so its expectations are only stable with the process pinned to
// UTC. vitest.config.js sets process.env.TZ and fe-test.sh passes -e TZ=UTC.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ago, agoShort, whenShort, describeCron, CRON_PRESETS } from '../time'

const FROM = new Date('2026-09-05T12:00:00Z')   // Fri 12:00 UTC, pinned

describe('environment', () => {
  it('runs in UTC (whenShort reads local getters)', () => {
    expect(new Date('2026-09-05T12:00:00Z').getHours()).toBe(12)
  })
})

// ── describeCron ────────────────────────────────────────────────────────────
// [expr, text | null, next ISO | null]
const TABLE = [
  ['*/30 * * * *', 'every 30 minutes', '2026-09-05T12:30:00.000Z'],
  ['0 * * * *', 'hourly at :00', '2026-09-05T13:00:00.000Z'],
  ['15 * * * *', 'hourly at :15', '2026-09-05T12:15:00.000Z'],
  ['0 */6 * * *', 'every 6 hours', '2026-09-05T18:00:00.000Z'],
  ['0 3 * * *', 'daily at 03:00', '2026-09-06T03:00:00.000Z'],
  ['0 9 * * mon-fri', 'weekdays at 09:00', '2026-09-07T09:00:00.000Z'],
  ['0 9 * * 1-5', 'every Tue, Wed, Thu, Fri, Sat at 09:00', '2026-09-08T09:00:00.000Z'],
  ['0 8 * * mon', 'every Monday at 08:00', '2026-09-07T08:00:00.000Z'],
  ['0 8 1 * *', 'monthly on the 1st at 08:00', '2026-10-01T08:00:00.000Z'],
  ['0 3 1,15 * *', 'at 03:00 on days 1,15 of every month', '2026-09-15T03:00:00.000Z'],
  ['0 2 * * 0', 'every Monday at 02:00', '2026-09-07T02:00:00.000Z'],           // seeded h1b_cron
  ['30 4 * jan,jul mon', 'at 04:30 in Jan, Jul on Mon', '2027-01-04T04:30:00.000Z'],
  ['* * * * *', 'every minute', '2026-09-05T12:01:00.000Z'],
  ['0 0 30 2 *', 'at 00:00 on day 30 in Feb', null],                            // never fires
  ['0 3 * *', null, null],                                                      // four fields
  ['0 8 * * 1', 'every Tuesday at 08:00', '2026-09-08T08:00:00.000Z'],
  ['0,30 9-17 * * mon-fri', 'at minute 0,30 of hour 9-17 on Mon, Tue, Wed, Thu, Fri', '2026-09-07T09:00:00.000Z'],
  ['5 4 * * sun', 'every Sunday at 04:05', '2026-09-06T04:05:00.000Z'],
  ['0 3 last * *', '0 3 last * *', null],                                       // APScheduler extension, echoed
  ['99 3 * * *', null, null],                                                   // minute out of range
  ['0 3 lastw * *', '0 3 lastw * *', null],                                     // extension, echoed
  ['0 3 * * fri#3', '0 3 * * fri#3', null],                                     // extension, echoed
  ['0 3 ? * *', null, null],                                                    // from_crontab refuses "?"
  ['0 3 * * last', null, null],                                                 // "last" is day-of-month
  ['0 3 * * last sun', null, null],                                             // six fields
]

describe('describeCron — the pinned table (rows 1-20)', () => {
  TABLE.forEach(([expr, text, next], i) => {
    it(`row ${i + 1}: ${JSON.stringify(expr)}`, () => {
      const r = describeCron(expr, { from: FROM })
      if (text === null) { expect(r).toBeNull(); return }
      expect(r).not.toBeNull()
      expect(r.text).toBe(text)
      expect(next === null ? r.next : r.next && r.next.toISOString()).toBe(next)
    })
  })
})

describe('describeCron — shape and guards', () => {
  it('marks an APScheduler-only extension `unparsed`, not invalid', () => {
    // "we did not read this" must not be rendered as "this can never fire".
    // Every expression here is one `CronTrigger.from_crontab` accepts (checked
    // against apscheduler 3.10.4 in the container) — that is the bar for echoing.
    for (const e of ['0 3 last * *', '0 3 lastw * *', '0 3 last-5 * *', '0 3 15,last * *',
                     '0 3 * * fri#3', '0 3 * * mon#2,fri', '0 3 last * mon']) {
      const r = describeCron(e, { from: FROM })
      expect(r, e).toEqual({ text: e, next: null, unparsed: true })
    }
  })
  it('does NOT echo what the backend would refuse (R4-E2E-05)', () => {
    // Settings validates a saved cron with backend/seed.py `_cron_error`, i.e.
    // `CronTrigger.from_crontab`. Anything it rejects has to read as invalid here
    // too, or the field promises a schedule the PATCH then bounces. The reasons
    // from_crontab gives, in order: Unrecognized expression "?" / "5w" / "1st"
    // for field "day"; Invalid weekday name "last"; Unrecognized expression
    // "4#2" for field "day_of_week".
    for (const e of ['0 3 ? * *', '0 3 * * ?', '0 3 5W * *', '0 3 1st * *',
                     '0 3 * * last', '0 3 * * 4#2']) {
      expect(describeCron(e, { from: FROM }), e).toBeNull()
    }
  })
  it('a SPACED extension (`last sun`) is six fields, so it reads as invalid', () => {
    // from_crontab refuses any field count but five, so the guard returning null
    // for `0 3 * * last sun` agrees with the backend — it is not an echo case.
    expect(describeCron('0 3 * * last sun', { from: FROM })).toBeNull()
    expect(describeCron('0 3 last sun * *', { from: FROM })).toBeNull()
  })
  it('a valid expression carries no `unparsed` flag', () => {
    expect(describeCron('0 3 * * *', { from: FROM }).unparsed).toBeUndefined()
  })
  it('returns null for empty / null / whitespace / non-5-field input', () => {
    for (const e of ['', '   ', null, undefined, '* * * *', '* * * * * *']) {
      expect(describeCron(e, { from: FROM })).toBeNull()
    }
  })
  it('rejects out-of-range values in every field rather than clamping', () => {
    for (const e of ['60 3 * * *', '0 24 * * *', '0 3 0 * *', '0 3 32 * *', '0 3 * 13 *', '0 3 * 0 *', '0 3 * * 7']) {
      expect(describeCron(e, { from: FROM })).toBeNull()
    }
  })
  it('rejects malformed steps and reversed ranges', () => {
    for (const e of ['*/0 * * * *', '*/x * * * *', '0 1/2/3 * * *', '0 9-5 * * *']) {
      expect(describeCron(e, { from: FROM })).toBeNull()
    }
  })
  it('trims and lower-cases before parsing', () => {
    expect(describeCron('  0 9 * * MON-FRI  ', { from: FROM }).text).toBe('weekdays at 09:00')
  })
  it('weekends is 5,6 under APScheduler numbering (Sat,Sun)', () => {
    expect(describeCron('0 9 * * sat,sun', { from: FROM }).text).toBe('weekends at 09:00')
  })
  it('falls back to `new Date()` when no `from` is given', () => {
    vi.useFakeTimers()
    try {
      vi.setSystemTime(FROM)
      expect(describeCron('0 3 * * *').next.toISOString()).toBe('2026-09-06T03:00:00.000Z')
    } finally { vi.useRealTimers() }
  })
  it('ignores an Invalid Date `from` by returning a null next', () => {
    const r = describeCron('0 3 * * *', { from: new Date('nope') })
    expect(r.text).toBe('daily at 03:00')
    expect(r.next).toBeNull()
  })
  it('day-of-month and day-of-week are ANDed, not ORed', () => {
    // 2026-09-15 is a Tuesday; `1,15` AND `tue` skips the 1st entirely
    const r = describeCron('0 3 1,15 * tue', { from: FROM })
    expect(r.text).toBe('at 03:00 on days 1,15 of every month and on Tue')
    expect(r.next.toISOString()).toBe('2026-09-15T03:00:00.000Z')
  })
  it('collapses a long expansion back to the raw field past eight values', () => {
    // 12 minutes -> the raw `*/5` says more than 0,5,10,… does; 8 hours still expand
    expect(describeCron('*/5 9-16 * * *', { from: FROM }).text)
      .toBe('at minute */5 of hour 9,10,11,12,13,14,15,16')
    // 9 hours tip over the limit and fall back to the raw field (table row 17)
    expect(describeCron('*/5 9-17 * * *', { from: FROM }).text).toBe('at minute */5 of hour 9-17')
  })
})

// ── whenShort ───────────────────────────────────────────────────────────────
describe('whenShort', () => {
  it('renders "Ddd DD Mon HH:MM" (UTC-pinned process)', () => {
    expect(whenShort(new Date('2026-09-05T12:30:00Z'))).toBe('Sat 05 Sep 12:30')
    expect(whenShort(new Date('2026-09-06T04:05:00Z'))).toBe('Sun 06 Sep 04:05')
    expect(whenShort(new Date('2026-09-07T08:00:00Z'))).toBe('Mon 07 Sep 08:00')
    expect(whenShort(new Date('2027-01-04T04:30:00Z'))).toBe('Mon 04 Jan 04:30')
  })
  it('zero-pads day, hour and minute', () => {
    expect(whenShort(new Date('2026-01-02T03:04:00Z'))).toBe('Fri 02 Jan 03:04')
  })
  it('guards non-Date input with an empty string', () => {
    for (const v of [null, undefined, '', 0, '2026-09-05T12:00:00Z', 1757073600000, {}, []]) {
      expect(whenShort(v)).toBe('')
    }
  })
  it('guards an Invalid Date with an empty string', () => {
    expect(whenShort(new Date('not a date'))).toBe('')
    expect(whenShort(new Date(NaN))).toBe('')
  })
  it('spells the day the same way describeCron pins it (Sep, not Sept)', () => {
    // the hand-written month table exists so the two halves of a schedule line agree
    expect(whenShort(describeCron('0 9 * * mon-fri', { from: FROM }).next)).toBe('Mon 07 Sep 09:00')
  })
})

// ── ago / agoShort ──────────────────────────────────────────────────────────
describe('ago / agoShort', () => {
  const NOW = new Date('2026-09-05T12:00:00Z')
  const back = (ms) => new Date(NOW.getTime() - ms).toISOString()
  const SEC = 1000, MIN = 60 * SEC, HOUR = 60 * MIN, DAY = 24 * HOUR

  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(NOW) })
  afterEach(() => { vi.useRealTimers() })

  it('returns "" for a falsy timestamp', () => {
    for (const v of [null, undefined, '', 0]) {
      expect(ago(v)).toBe('')
      expect(agoShort(v)).toBe('')
    }
  })
  it('under a minute', () => {
    for (const ms of [0, SEC, 59 * SEC]) {
      expect(ago(back(ms))).toBe('just now')
      expect(agoShort(back(ms))).toBe('now')
    }
  })
  it('minutes (1-59)', () => {
    expect(ago(back(MIN))).toBe('1m ago')
    expect(agoShort(back(MIN))).toBe('1m')
    expect(ago(back(59 * MIN + 59 * SEC))).toBe('59m ago')
    expect(agoShort(back(59 * MIN + 59 * SEC))).toBe('59m')
  })
  it('hours (1-23) — the 60-minute boundary', () => {
    expect(ago(back(60 * MIN))).toBe('1h ago')
    expect(agoShort(back(60 * MIN))).toBe('1h')
    expect(ago(back(23 * HOUR + 59 * MIN))).toBe('23h ago')
    expect(agoShort(back(23 * HOUR + 59 * MIN))).toBe('23h')
  })
  it('days — the 24-hour boundary', () => {
    expect(ago(back(DAY))).toBe('1d ago')
    expect(agoShort(back(DAY))).toBe('1d')
    expect(ago(back(3 * DAY + 5 * HOUR))).toBe('3d ago')
    expect(agoShort(back(90 * DAY))).toBe('90d')
  })
  it('a future timestamp reads as "just now" / "now", never a negative', () => {
    const ahead = new Date(NOW.getTime() + 5 * MIN).toISOString()
    expect(ago(ahead)).toBe('just now')
    expect(agoShort(ahead)).toBe('now')
  })
  it('accepts a Date-parseable string as well as a full ISO instant', () => {
    expect(ago('2026-09-05T09:00:00Z')).toBe('3h ago')
    expect(ago('2026-09-05T09:00:00')).toBe('3h ago')   // no zone -> local, and local is UTC here
  })
})

// ── presets ─────────────────────────────────────────────────────────────────
describe('CRON_PRESETS', () => {
  it('is seven [label, expression] pairs ending in Off', () => {
    expect(CRON_PRESETS).toHaveLength(7)
    for (const row of CRON_PRESETS) {
      expect(Array.isArray(row)).toBe(true)
      expect(row).toHaveLength(2)
      expect(typeof row[0]).toBe('string')
      expect(typeof row[1]).toBe('string')
    }
    expect(CRON_PRESETS[CRON_PRESETS.length - 1]).toEqual(['Off', ''])
  })
  it('has unique labels and unique expressions', () => {
    expect(new Set(CRON_PRESETS.map((r) => r[0])).size).toBe(CRON_PRESETS.length)
    expect(new Set(CRON_PRESETS.map((r) => r[1])).size).toBe(CRON_PRESETS.length)
  })
  it('every non-Off preset parses and names a real next fire', () => {
    for (const [, expr] of CRON_PRESETS.filter(([, e]) => e)) {
      const r = describeCron(expr, { from: FROM })
      expect(r, expr).not.toBeNull()
      expect(r.text.length, expr).toBeGreaterThan(0)
      expect(r.next, expr).toBeInstanceOf(Date)
    }
  })
  it('uses weekday NAMES, never digits (D-20: 1 would mean Tuesday)', () => {
    // `0 8 * * mon` and `0 8 * * 1` describe different days under APScheduler
    expect(CRON_PRESETS.map(([, e]) => e)).toContain('0 8 * * mon')
    expect(describeCron('0 8 * * mon', { from: FROM }).text).toBe('every Monday at 08:00')
    expect(describeCron('0 8 * * 1', { from: FROM }).text).toBe('every Tuesday at 08:00')
    for (const [label, expr] of CRON_PRESETS) {
      if (!expr) continue
      const dow = expr.split(/\s+/)[4]
      expect(/^\d/.test(dow), `${label} names its weekday field with digits`).toBe(false)
    }
  })
  it('the labels agree with what describeCron reads back', () => {
    const say = (e) => describeCron(e, { from: FROM }).text
    expect(say('0 * * * *')).toBe('hourly at :00')                  // Hourly
    expect(say('0 */6 * * *')).toBe('every 6 hours')                // Every 6 hours
    expect(say('0 3 * * *')).toBe('daily at 03:00')                 // Daily 03:00
    expect(say('0 9 * * mon-fri')).toBe('weekdays at 09:00')        // Weekdays 09:00
    expect(say('0 8 * * mon')).toBe('every Monday at 08:00')        // Weekly Monday 08:00
    expect(say('0 8 1 * *')).toBe('monthly on the 1st at 08:00')    // Monthly 1st 08:00
  })
})
