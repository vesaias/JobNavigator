# Round 3 — items reported by the user (2026-09-04)

### R3-U-01 · P3 · Stats funnel (funnel mode) uses different stage colours than Applications and the Flow view
**Where** `frontend/src/v2/Stats.jsx` funnel renderer vs the stage colour tokens used by `Applications.jsx` (`--stage-*`) and the Sankey/Flow view on the same card.
**Actual** (user report) the funnel bars for Applied / Interview / Offer / Rejected are not the same colours as the stage chips on Applications and the Flow diagram.
**Expected** one stage → one colour everywhere: funnel, Flow, Applications board, KPI tiles.
**Proposed fix** drive all three from the same `--stage-<name>` tokens in `theme.css`; measure the computed fill per stage on Stats (both modes) and Applications and assert equality.
**Status** fixed (8804ae3), verified live 2026-09-04 (`round3/verify.md`).

### R3-U-02 · P3 · "Applied" line on the jobs timeline is visually identical to "New" (both dark)
**Where** `frontend/src/v2/Stats.jsx` — the Jobs discovered timeline (Recharts lines), `--stage-applied` line added in round 1 (STAT-06/07).
**Actual** (user report) the Applied and New series render in two dark colours that cannot be told apart, in at least one theme.
**Expected** the Applied series uses the Applied stage colour (same token as R3-U-01) and New uses a clearly distinct one; legend matches.
**Proposed fix** assign `stroke: var(--stage-applied)` to Applied and `var(--accent)`/`--text-2` to New (or vice versa), check contrast between the two strokes in both themes (ΔE or simple luminance gap), and measure.
**Status** fixed (8804ae3), verified live 2026-09-04 (`round3/verify.md`).

### R3-U-03 · P3 · Companies rows hover to the green wash while Feed and Applications rows hover to `--surface-2`
**Status** fixed (406aebe): `.v2-crow:hover` and the pinned actions cell on `--surface-2`; verified equal to Feed/Applications row hover (`round3/verify-final.md`).

### R3-U-04 · P3 · Focus ring rectangle on every input on mouse click; flat search inputs show a floating rectangle
**Status** fixed (406aebe): input focus is the app's own accent border/underline, no box-shadow; bare inputs signal on their `v2-fieldwrap` wrapper; keyboard ring kept on non-input controls. Verified on 9 inputs (`round3/verify-final.md`).

### R3-U-05 · P4 · Feed and Applications header filter buttons have no hover
**Status** fixed (406aebe): `v2-bd` on the dropdown triggers, `v2-hover-accent-text` on Sort, `v2-hover-accent` on stage group headers; verified (`round3/verify-final.md`).

### R3-U-06 · P4 · Cover Letters "Archived" band hovers differently from the Résumés band
**Status** fixed (406aebe): both bands use `.v2-act`; computed styles byte-identical at rest and on hover (`round3/verify-final.md`).
