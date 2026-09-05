// One clock for every v2 screen, so the list and the editor never disagree about the same timestamp.
const mins = (iso) => (iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 60000) : null)
export const ago = (iso) => {
  const m = mins(iso); if (m == null) return ''
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`
}
export const agoShort = (iso) => {
  const m = mins(iso); if (m == null) return ''
  if (m < 1) return 'now'
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`
}

// whenShort's "Sat 06 Sep 05:00" shape matches Stats' toLocaleString('en-GB')
// output by hand, since ICU's own formatting (e.g. "Sept") would make the two halves of a schedule line disagree on how a day is named.

// ── cron ────────────────────────────────────────────────────────────────────
// describeCron(expr): plain-English sentence + next fire time for one Scheduler
// cron field. Pure, no dependency. Two backend-verified departures from standard
// cron: weekday numbers are APScheduler's, not vixie cron's (0=Monday — `0 8 * * 1`
// fires Tuesday in the container), and day-of-month/day-of-week are ANDed, not
// ORed (`next` follows APScheduler). `next` is computed in UTC (the scheduler has
// no timezone) and returned as a Date; callers render it in the reader's own
// zone via `whenShort`. Returns `{ text, next }`, or null if unreadable;
// an APScheduler-only extension (`last`, `fri#3`) this parser doesn't evaluate
// is echoed as `{ text: <raw line>, unparsed: true }` rather than called invalid.
const DOW_NAMES = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']   // APScheduler order: index 0 = Monday
const DOW_FULL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const DOW_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MON_NAMES = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
const MON_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad2 = (n) => String(n).padStart(2, '0')
export const whenShort = (d) => {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return ''
  // local getters on purpose: the Date is a UTC instant, read in the viewer's zone
  return `${DOW_SHORT[(d.getDay() + 6) % 7]} ${pad2(d.getDate())} ${MON_SHORT[d.getMonth()]} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}
const ord = (n) => {
  const s = ['th', 'st', 'nd', 'rd']; const v = n % 100
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`
}

// one token → its number, by digits or by three-letter name. Out of range is a
// hard failure (the backend refuses the same value), never a clamp.
const tokenNum = (t, min, max, names) => {
  let v = NaN
  if (/^\d+$/.test(t)) v = parseInt(t, 10)
  else if (names) { const i = names.indexOf(t.slice(0, 3)); if (i >= 0) v = i + min }
  return Number.isInteger(v) && v >= min && v <= max ? v : null
}

// `*` · `a` · `a-b` · `*/n` · `a-b/n` · `a/n` · any of those in a comma list.
// Returns the expanded set plus the two shapes the sentence builder asks about:
// `star` (the whole field is `*`) and `step` (the whole field is `*/n`).
function parseField(spec, min, max, names) {
  const raw = String(spec).trim().toLowerCase()
  if (!raw) return null
  const out = new Set()
  for (const term of raw.split(',')) {
    const slash = term.split('/')
    if (slash.length > 2) return null
    const body = slash[0]
    let step = 1
    if (slash.length === 2) {
      if (!/^\d+$/.test(slash[1])) return null
      step = parseInt(slash[1], 10)
      if (step < 1) return null
    }
    let lo; let hi
    if (body === '*') { lo = min; hi = max } else {
      const bits = body.split('-')
      if (bits.length > 2) return null
      const a = tokenNum(bits[0], min, max, names)
      if (a === null) return null
      if (bits.length === 1) { lo = a; hi = slash.length === 2 ? max : a } else {
        const b = tokenNum(bits[1], min, max, names)
        if (b === null) return null
        lo = a; hi = b
      }
    }
    if (lo > hi) return null                       // no wrap-around: APScheduler refuses it too
    for (let v = lo; v <= hi; v += step) out.add(v)
  }
  const list = [...out].sort((a, b) => a - b)
  if (!list.length) return null
  const stepAll = /^\*\/(\d+)$/.exec(raw)
  return { raw, list, set: out, star: raw === '*', step: stepAll ? parseInt(stepAll[1], 10) : 0 }
}

// keep a long list out of the sentence — past eight values the raw field says
// more than its expansion does
const fieldTxt = (F) => (F.list.length <= 8 ? F.list.join(',') : F.raw)

function cronText(M, H, D, MO, W) {
  const hm = (h, m) => `${pad2(h)}:${pad2(m)}`
  const one = (F) => F.list.length === 1
  const anyDay = D.star && MO.star && W.star

  // the seven shapes worth a plain sentence
  if (anyDay) {
    if (H.star && (M.star || M.step === 1)) return 'every minute'
    if (H.star && M.step) return `every ${M.step} minutes`
    if (H.star && one(M)) return `hourly at :${pad2(M.list[0])}`
    if (H.step && one(M)) {
      const base = H.step === 1 ? 'every hour' : `every ${H.step} hours`
      return M.list[0] === 0 ? base : `${base} at :${pad2(M.list[0])}`
    }
    if (one(M) && one(H)) return `daily at ${hm(H.list[0], M.list[0])}`
  }
  if (one(M) && one(H)) {
    const at = `at ${hm(H.list[0], M.list[0])}`
    if (D.star && MO.star && !W.star) {
      const k = W.list.join(',')
      if (k === '0,1,2,3,4') return `weekdays ${at}`         // 0 = Monday (see the note above)
      if (k === '5,6') return `weekends ${at}`
      if (one(W)) return `every ${DOW_FULL[W.list[0]]} ${at}`
      return `every ${W.list.map((d) => DOW_SHORT[d]).join(', ')} ${at}`
    }
    if (MO.star && W.star && one(D)) return `monthly on the ${ord(D.list[0])} ${at}`
  }

  // …and the generic reading for everything else
  let timePart
  const times = []
  for (const h of H.list) for (const m of M.list) times.push(hm(h, m))
  if (one(M) && one(H)) timePart = `at ${hm(H.list[0], M.list[0])}`
  else if (one(M) && H.star) timePart = `at :${pad2(M.list[0])} every hour`
  else if (one(M) && H.step) timePart = `at :${pad2(M.list[0])} every ${H.step} hours`
  else if (times.length <= 6) timePart = `at ${times.join(', ')}`
  else timePart = `at minute ${fieldTxt(M)} of hour ${fieldTxt(H)}`

  const segs = [timePart]
  if (!D.star) segs.push(`on ${D.list.length > 1 ? 'days' : 'day'} ${fieldTxt(D)}`)
  if (!MO.star) segs.push(`in ${MO.list.map((m) => MON_SHORT[m - 1]).join(', ')}`)
  else if (!D.star) segs.push('of every month')
  // "and on" where a day-of-month is also set: APScheduler ANDs the two fields
  if (!W.star) segs.push(`${D.star ? 'on' : 'and on'} ${W.list.map((d) => DOW_SHORT[d]).join(', ')}`)
  return segs.join(' ')
}

// Day by day rather than minute by minute: at most ~3000 iterations, which is
// the widest real gap (29 February can be eight years out).
function cronNext(M, H, D, MO, W, from) {
  const base = from instanceof Date ? from : new Date()
  if (Number.isNaN(base.getTime())) return null
  const floor = Math.floor(base.getTime() / 60000) * 60000 + 60000   // the next whole minute
  const s = new Date(floor)
  const y = s.getUTCFullYear(); const mo = s.getUTCMonth(); const d0 = s.getUTCDate()
  for (let i = 0; i < 3000; i++) {
    const day = new Date(Date.UTC(y, mo, d0 + i))
    if (!MO.set.has(day.getUTCMonth() + 1)) continue
    if (!D.set.has(day.getUTCDate())) continue
    if (!W.set.has((day.getUTCDay() + 6) % 7)) continue             // JS 0=Sun → APScheduler 0=Mon
    for (const h of H.list) {
      for (const m of M.list) {
        const t = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), h, m)
        if (t >= floor) return new Date(t)
      }
    }
  }
  return null
}

// APScheduler's own extras (`last`, `last sun`, `fri#3`, `?`) are legal on the
// backend but not evaluated here, so the line falls back to echoing the expression.
const CRON_EXTRAS = /[#?]|(^|[^a-z])(last|w)([^a-z]|$)/i

export function describeCron(expr, opts = {}) {
  const raw = String(expr == null ? '' : expr).trim()
  if (!raw) return null
  const parts = raw.split(/\s+/)
  if (parts.length !== 5) return null
  // `unparsed` separates "we did not read this" from "this can never fire" —
  // both carry a null `next`, and the row must not call the first one dead
  if (CRON_EXTRAS.test(raw)) return { text: raw, next: null, unparsed: true }
  const M = parseField(parts[0], 0, 59)
  const H = parseField(parts[1], 0, 23)
  const D = parseField(parts[2], 1, 31)
  const MO = parseField(parts[3], 1, 12, MON_NAMES)
  const W = parseField(parts[4], 0, 6, DOW_NAMES)
  if (!M || !H || !D || !MO || !W) return null
  return { text: cronText(M, H, D, MO, W), next: cronNext(M, H, D, MO, W, opts.from) }
}

// Presets use names (mon-fri, mon) not digits: under APScheduler's numbering
// 1-5/1 mean Tue-Sat/Tuesday, so digits would mislabel the schedule (DECISIONS D-20).
export const CRON_PRESETS = [
  ['Hourly', '0 * * * *'],
  ['Every 6 hours', '0 */6 * * *'],
  ['Daily 03:00', '0 3 * * *'],
  ['Weekdays 09:00', '0 9 * * mon-fri'],
  ['Weekly Monday 08:00', '0 8 * * mon'],
  ['Monthly 1st 08:00', '0 8 1 * *'],
  ['Off', ''],
]

// ── describeCron, checked ───────────────────────────────────────────────────
// There is no test runner for the frontend, so this table is run by hand and its
// output pasted back. It is a real run, not a desk check — copy this file to
// `time.mjs`, then (node ≥ 18):
//
//   import { describeCron } from './time.mjs'
//   const FROM = new Date('2026-09-05T12:00:00Z')          // Fri 12:00 UTC, pinned
//   for (const e of TABLE) { const r = describeCron(e, { from: FROM })
//     console.log(e, '|', r ? r.text : 'NULL', '|', r && r.next ? r.next.toISOString() : '—') }
//
// `next` below is the UTC instant the Date holds; the Settings row prints it
// through `whenShort`, i.e. in the reader's own zone. Rows 6/7, 8/16 and 11 are
// the weekday-numbering evidence: the same schedule written with a NAME and with
// a DIGIT lands on different days, and the digits agree with what APScheduler
// 3.10.4 actually returned in the container (`0 8 * * 1` → Tue 08 Sep).
//
//  #  expression              text                                                    next (UTC)
//  1  */30 * * * *            every 30 minutes                                        2026-09-05 12:30
//  2  0 * * * *               hourly at :00                                           2026-09-05 13:00
//  3  15 * * * *              hourly at :15                                           2026-09-05 12:15
//  4  0 */6 * * *             every 6 hours                                           2026-09-05 18:00
//  5  0 3 * * *               daily at 03:00                                          2026-09-06 03:00
//  6  0 9 * * mon-fri         weekdays at 09:00                                       2026-09-07 09:00
//  7  0 9 * * 1-5             every Tue, Wed, Thu, Fri, Sat at 09:00                  2026-09-08 09:00
//  8  0 8 * * mon             every Monday at 08:00                                   2026-09-07 08:00
//  9  0 8 1 * *               monthly on the 1st at 08:00                             2026-10-01 08:00
// 10  0 3 1,15 * *            at 03:00 on days 1,15 of every month                    2026-09-15 03:00
// 11  0 2 * * 0               every Monday at 02:00        (the seeded h1b_cron)      2026-09-07 02:00
// 12  30 4 * jan,jul mon      at 04:30 in Jan, Jul on Mon                             2027-01-04 04:30
// 13  * * * * *               every minute                                            2026-09-05 12:01
// 14  0 0 30 2 *              at 00:00 on day 30 in Feb                               null — never fires
// 15  0 3 * *                 NULL (four fields)                                      —
// 16  0 8 * * 1               every Tuesday at 08:00                                  2026-09-08 08:00
// 17  0,30 9-17 * * mon-fri   at minute 0,30 of hour 9-17 on Mon, Tue, Wed, Thu, Fri  2026-09-07 09:00
// 18  5 4 * * sun             every Sunday at 04:05                                   2026-09-06 04:05
// 19  0 3 last * *            0 3 last * *                 (extension, echoed)        null
// 20  99 3 * * *              NULL (minute out of range)                              —
