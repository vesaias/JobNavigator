# reconcile D5 (D4f → D5, after the ca7313c crash fix)

Pixel: 18 shots changed. Persona ~120 k px (both columns shift 1 px: column headers `Heading strong` 18 px line-height 26 → 27), Résumés shelf 22–35 k (card titles 19 px: 28 → 26, cards 62 → 60), Stats 10–11 k (card titles 17 px: 24 → 25), everything else ≤ 22 px (noise floor).
Style: 66 changed tuples, 0 missing, 0 added — every row is a `Heading strong` line-height pin (26/27/25 px) or the 1–2 px container cascade around it; all listed in `expected-D5.md` (eleven card-title boxes). No colour, border, radius or hover change anywhere. No control changed height.
Verdict: **0 unexpected**. Reconciled by the orchestrator from the grouped diff (small enough not to need an agent).
Earlier D5 build: Persona and the résumé editor were blank (`RemoveX is not defined`) — caught by the pixel diff (100 % changed) and the crawl (0 elements); fixed in `ca7313c`.
