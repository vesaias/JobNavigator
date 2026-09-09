// Feed activity: what a job's in-flight runs mean on screen. A report that exists
// is never hidden by a run; activity lives in the band, the tabs and the ✦ mark.
// Inputs: job.in_flight (job types) and job.in_flight_detail ([{ job_type, meta }]);
// meta is { resume_names, depth } for scoring, { base_name, replaces } for tailoring,
// or null (older run), in which case everything degrades to "Scoring…" / "Tailoring…".

export const ANALYZE = 'analyze_job'
export const SCORE_RESUME = 'score_resume'   // the Resume editor's score button, lands under "Tailored"
export const TAILOR = 'tailor_resume'
// The tailored score always lands under this fixed key (JobFeed's isTailoredName).
// "{base} → {company}" is a LABEL for the ghost tab and the activity line, never a key.
export const TAILORED_KEY = 'Tailored'

const list = (v) => (Array.isArray(v) ? v : [])

/** The one read of a job's runs: what is running, and what it is running on. */
export function feedActivity(job) {
  const flight = list(job && job.in_flight)
  const detail = list(job && job.in_flight_detail).filter((d) => d && d.job_type)
  // union of both fields: an optimistic write sets them together, but a poll
  // against an older backend answers with in_flight only, and a detail row
  // without its plain entry must still count as running.
  const types = new Set([...flight, ...detail.map((d) => d.job_type)])
  const metaOf = (t) => {
    const hit = detail.find((d) => d.job_type === t)
    return hit && hit.meta ? hit.meta : null
  }
  const running = types.has(ANALYZE) || types.has(SCORE_RESUME)
  const tailoring = types.has(TAILOR)
  const aMeta = running ? (metaOf(ANALYZE) || metaOf(SCORE_RESUME)) : null
  const tMeta = tailoring ? metaOf(TAILOR) : null
  const rescoreNames = list(aMeta && aMeta.resume_names).filter((n) => typeof n === 'string' && n)
  const baseName = (tMeta && typeof tMeta.base_name === 'string' && tMeta.base_name) || ''
  return {
    running,
    tailoring,
    active: running || tailoring,
    rescoreNames,
    depth: (aMeta && aMeta.depth) || null,   // Light vs Full is not drawn; carried for titles only
    baseName,
    // no meta: fall back to the job's own state, which is what "replaces" means
    replaces: tMeta ? !!tMeta.replaces : !!(job && job.tailored_resume_id),
    // scoring owns the ink when both run — the score is the thing the band is about
    tone: running ? 'accent' : tailoring ? 'ai' : null,
  }
}

/** The band's trailing line: "Scoring 2 résumés · Tailoring from Backend base". */
export function activityText(act) {
  const parts = []
  if (act.running) {
    const n = act.rescoreNames.length
    parts.push(n ? `Scoring ${n} résumé${n === 1 ? '' : 's'}` : 'Scoring…')
  }
  if (act.tailoring) {
    const verb = act.replaces ? 'Re-tailoring' : 'Tailoring'
    parts.push(act.baseName ? `${verb} from ${act.baseName}` : `${verb}…`)
  }
  return parts.join(' · ')
}

/** The card's ✦ mark while a tailor runs — the only card state activity owns. */
export function tailorMarkTitle(act) {
  if (!act.replaces) return 'Tailoring a résumé for this job…'
  return act.baseName
    ? `Re-tailoring from ${act.baseName} · replaces the current tailored résumé`
    : 'Re-tailoring · replaces the current tailored résumé'
}

/**
 * A report tab that is itself in the run: null, or the ink it spins in.
 * `tab` is one of JobFeed's report rows ({ name, tailored }).
 */
export function tabBusy(act, tab) {
  if (act.tailoring && tab.tailored) return 'ai'
  if (act.running && act.rescoreNames.includes(tab.name)) return 'accent'
  return null
}

export const tabBusyHint = (tone) => (tone === 'ai' ? ' · re-tailoring' : tone ? ' · scoring again' : '')

/**
 * Tabs for résumés that are in the run but have no report yet — dashed, muted,
 * not clickable, replaced by the real tab when the run lands. `reports` is
 * JobFeed's derived list; `company` names the tailored ghost.
 */
export function ghostTabs(act, reports, company) {
  const have = new Set(list(reports).map((r) => r.name))
  const out = act.rescoreNames
    .filter((n) => !have.has(n))
    .map((n) => ({ key: n, label: n, tailored: false }))
  // the tailored ghost needs a base name to be worth drawing: "→ Acme" alone says nothing
  if (act.tailoring && act.baseName && !have.has(TAILORED_KEY)) {
    out.push({ key: `${TAILORED_KEY}:ghost`, label: `${act.baseName} → ${company || 'this job'}`, tailored: true })
  }
  return out
}

/**
 * The poll answers `{id: ["analyze_job"]}` without ?detail=1 and
 * `{id: [{job_type, meta}]}` with it. Both shapes normalise here, so a backend
 * that ignores the flag still drives the plain states.
 */
export const flightTypes = (rows) => list(rows).map((r) => (typeof r === 'string' ? r : r && r.job_type)).filter(Boolean)
export const flightDetail = (rows) => list(rows)
  .map((r) => (typeof r === 'string' ? { job_type: r, meta: null } : r))
  .filter((r) => r && r.job_type)
  .map((r) => ({ job_type: r.job_type, meta: r.meta || null }))
