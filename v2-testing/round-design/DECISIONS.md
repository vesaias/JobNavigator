# Decisions log — skins, cron, round 4

One entry per question. Status: **needs decision** · **decided: …** (with the date). Workers add entries here instead of guessing; contradictions between the handoff, the code and earlier decisions go here too.

## Open

- **D-01 Persona import · `current_company`** — seed it from the most recent role in the imported résumé, or leave blank? (asked 2026-09-04, twice). **needs decision**
- **D-02 Theme picker list** — keep Default · Editorial · Cobalt · SaaS · Win98 only (Tone 1–3 stay in `theme.css`, out of the picker); Alt kept or dropped? **needs decision**
- **D-03 Theme picker widget** — Select (today) or a swatch row (five tiles, ground + accent + font initial, active ringed)? **needs decision**
- **D-04 Theme labels** — keep ours ("Cobalt", "SaaS", "Win98") or the board names from the handoff ("Cobalt — 2.0 §3a", "SaaS — ModernSaaS + v1")? Recommendation: ours. **needs decision**
- **D-05 Reduced motion** — the handoff's `prefers-reduced-motion` rule zeroes every animation, including spinners. Recommendation: apply it to transitions only; spinners keep turning. **needs decision**
  - *implemented (S3, ui.jsx pass), the recommendation only*: `@media (prefers-reduced-motion: reduce) { .jn-v2 * { transition-duration:0s !important } }` at the foot of `theme.css`. The handoff's `animation-duration:0s` half is **not** landed — it would stop `.v2-spin` and the ScoreRing busy arc, which are progress indicators, not decoration. Adding that half back is one declaration if the decision goes the other way.
- **D-06 Field hover** — the handoff proposes a rest→hover border on Input/Select/SearchInput/ToolbarTrigger (`--input-border-hover`), marked P. Accept for the default theme too, or only where a theme sets it? Recommendation: accept everywhere. **needs decision**
  - *implemented inert (S3)*: the rule is live —`.jn-v2 .v2-inset:not(.v2-underline):not([aria-expanded="true"]):hover:not(:focus)` — but the base blocks point `--input-border-hover` at `var(--input-border)`, the field's own rest border, so it repaints nothing in the default theme. cobalt/saas keep the handoff's `var(--text-2)`; win98's `none` still needs re-pointing at its rest border (`--input-border`) before it means anything. Accepting is one value in two base blocks (`var(--line-strong)`).
  - Three carve-outs came out of the wiring, and they stand whatever the decision: the SearchInput **underline** variant rests on `--input-underline`, an **open** Select trigger already wears `--input-border-focus`, and field **wrappers** are excluded because LoginModal paints its wrapper `--bad` while an error stands.
- **D-07 Pressed states** — proposed on every control (1 px shift + wash; bevel flip on Win98). Accept for the default theme? Recommendation: accept. **needs decision**
  - *implemented inert (S3)*: `.v2-bd/.v2-bdc/.v2-act:active` and `.v2-btn-primary:active` are live, but the base blocks set `--pressed-shift: none`, `--pressed-wash: transparent` and `--btn-primary-pressed-bg: var(--btn-primary-bg)`, so nothing shifts or washes here. The skins carry the handoff's values. Accepting is three values in two base blocks.
  - One deviation from the generated stylesheet: the wash is painted as a flat two-stop `background-image` overlay rather than `background:`. `background: transparent !important` would *erase* a Card's own surface for as long as the mouse is down; an opaque skin wash paints identically either way.
- **D-08 Disabled paint** — the handoff's blanket `.5` opacity on `[aria-disabled]` would replace the token-swap dimming (grey on muted) that was decided in the design pass. Recommendation: keep the token swap for Button, use opacity for the rest. **needs decision**
  - *implemented as recommended, pixel-neutral (S3)*: Button keeps its token swap untouched (and writes `opacity:1` explicitly, so the class rule cannot reach it). Every other primitive now writes `opacity: var(--disabled-opacity)` inline — and `.5` **is** the number each of them already wrote, so the base value stays `.5` and the default theme does not move. `.jn-v2 [aria-disabled="true"]` is landed as the fallback for hand-rolled disabled spans in the screens.
  - Two notes for whoever closes this: `--disabled-ink` had to become `inherit` in the base blocks (at `var(--muted)` the rule would have repainted any disabled control that sets no colour of its own); and because every primitive's dim is *inline*, win98's engraved treatment (`--disabled-ink` `#808080` + `--disabled-engrave`) cannot reach a control that sets its own colour. Making that work is a per-primitive `color` read, not a cascade change.
  - Four controls keep a literal because their dim is not `.5`: Input/Textarea/Select `.6`, ChoiceCard/ChoiceRow `.45`, MoveArrows `.35`, Button-busy `.6`.
- **D-11 Primary/danger hover (U-02)** — the board tags the filled buttons' hover **P**: today a primary or danger button does not change on hover at all, and the handoff proposes `color-mix(… 90%, black)`. *implemented inert (S3)*: `Button` now carries `v2-btn-primary` / `v2-btn-danger` and the rules are live, but `--btn-primary-hover-bg` / `--btn-danger-hover-bg` resolve to the button's own rest paint in the base blocks. The three boards carry the darkening; `editorial`, `alt` and the tone ramp are palette-only blocks, so they inherit the inert base and get no hover either. **needs decision**
- **D-12 Rail active mark width** — the handoff's `--rail-active-mark` is `2px solid var(--rail-accent)`; V2App has drawn **3 px** since the design pass (and pads its items 1 px short to compensate, so the labels do not shift). *Taken as 3 px in the base blocks* to keep the pass pixel-neutral — the generated `skins.js` should follow, or the padding compensation has to go with it. **needs decision**
- **D-09 Extension popup** — keeps its own `data-theme` (light/dark) as a separate document. Align to `data-appearance`? Recommendation: leave. **needs decision**
- **D-10 T4 soak length** — 24 h or 3 days? **needs decision**

## Decided

- Skins may set radius, shadow, border width and type (2026-09-05).
- Vocabulary: the twelve cover-all decisions in `round2/text-suggestions.md` §0 (2026-09-05).
- Settings rows renamed Appearance (light/dark/system) and Theme (look); section title Display; storage keys migrated (2026-09-05).
- Release order: skins → cron helper → comment cleanup (frontend + backend) → round 4 → release. Multitenancy dropped from the plan (2026-09-05).
