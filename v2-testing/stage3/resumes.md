# Stage 3 — Résumés (Shelf + Editor)
Tested: 2026-09-02, bundle index-Dnrx3n0f.js (HEAD f60ec5e, on top of 9ed8963), themes light+dark, viewport 1440×900 (+ one narrow 1024×700 pass)
Design: `v2-testing/design/Resumes Home D.dc.html`   Inventory: `v2-testing/inventory/v2-resumes.md`   Scripts: `res_1_shelf.py`, `res_2_add.py`, `res_3_sections.py`, `res_4_pdf.py`, `res_5_tailor.py`, `res_6_menu.py`, `res_7_narrow.py` (scratchpad; copied to `/tmp/v2t/` in the backend container)

Live data at test time: 4 bases (PM 45 live / 255 archived · TPgM 0/0 · PjM 2/1 · PjM FinTech 0/1), Persona 2 live / 39 archived, `total_copies` 49, `archived` 296, `GET /resumes?is_base=false` 345 = 49 + 296. Rail badge reads `GET /resumes?is_base=true` → 4.

## Findings

(appended as the pass progresses)

## Fixed in source

## Couldn't test

## Scratch data
- (running list — must end empty)
