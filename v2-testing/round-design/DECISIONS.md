# Decisions log — skins, cron, round 4

One entry per question. Status: **needs decision** · **decided: …** (with the date). Workers add entries here instead of guessing; contradictions between the handoff, the code and earlier decisions go here too.

## Open

- **D-01 Persona import · `current_company`** — seed it from the most recent role in the imported résumé, or leave blank? (asked 2026-09-04, twice). **needs decision**
- **D-02 Theme picker list** — keep Default · Editorial · Cobalt · SaaS · Win98 only (Tone 1–3 stay in `theme.css`, out of the picker); Alt kept or dropped? **needs decision**
- **D-03 Theme picker widget** — Select (today) or a swatch row (five tiles, ground + accent + font initial, active ringed)? **needs decision**
- **D-04 Theme labels** — keep ours ("Cobalt", "SaaS", "Win98") or the board names from the handoff ("Cobalt — 2.0 §3a", "SaaS — ModernSaaS + v1")? Recommendation: ours. **needs decision**
- **D-05 Reduced motion** — the handoff's `prefers-reduced-motion` rule zeroes every animation, including spinners. Recommendation: apply it to transitions only; spinners keep turning. **needs decision**
- **D-06 Field hover** — the handoff proposes a rest→hover border on Input/Select/SearchInput/ToolbarTrigger (`--input-border-hover`), marked P. Accept for the default theme too, or only where a theme sets it? Recommendation: accept everywhere. **needs decision**
- **D-07 Pressed states** — proposed on every control (1 px shift + wash; bevel flip on Win98). Accept for the default theme? Recommendation: accept. **needs decision**
- **D-08 Disabled paint** — the handoff's blanket `.5` opacity on `[aria-disabled]` would replace the token-swap dimming (grey on muted) that was decided in the design pass. Recommendation: keep the token swap for Button, use opacity for the rest. **needs decision**
- **D-09 Extension popup** — keeps its own `data-theme` (light/dark) as a separate document. Align to `data-appearance`? Recommendation: leave. **needs decision**
- **D-10 T4 soak length** — 24 h or 3 days? **needs decision**

## Decided

- Skins may set radius, shadow, border width and type (2026-09-05).
- Vocabulary: the twelve cover-all decisions in `round2/text-suggestions.md` §0 (2026-09-05).
- Settings rows renamed Appearance (light/dark/system) and Theme (look); section title Display; storage keys migrated (2026-09-05).
- Release order: skins → cron helper → comment cleanup (frontend + backend) → round 4 → release. Multitenancy dropped from the plan (2026-09-05).
