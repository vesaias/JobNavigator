# Cron helper — v2 Settings / Scheduler

Verified against the running stack (Playwright inside the backend container,
`http://caddy`) via `v2-testing/tools/h.py` + a one-off script
(`/tmp/v2t/cronchk.py`, not checked in). Five cron rows: Auto-reject, DB
backup, Telegram digest, H-1B refresh, Job cleanup.

Originals recorded from `GET /api/settings` before touching anything, and
restored via `PATCH /api/settings` at the end — confirmed by a follow-up GET:

| key | value |
|---|---|
| reject_cron | `0 4 * * *` |
| backup_cron | `0 3 * * *` |
| digest_cron | `0 18 * * *` |
| h1b_cron | `0 2 * * 0` |
| cleanup_cron | `15 4 * * *` |

## Steps · result · evidence

**1. Record originals (`GET /api/settings`)** — pass. Values above.

**2. Screenshot Scheduler section, light, 1440** — pass.
`v2-testing/artifacts/design/cron1.png`. All five rows render: label,
helper description, `next …` line, mono field, "Preset ▾" trigger at 24px
beside the field. Row heights measured via `getBoundingClientRect()` on
each row's root element: all five cron rows are exactly **70px** — stable,
no jitter from the two-line helper vs. the single-line interval rows above
them (52-56px, expected since they carry no `next` line).

**3. DB backup field — live update / validation / clear** — pass, all sub-checks:
- Typed `0 */6 * * *`: helper updated **before blur** to
  `every 6 hours UTC · next Sat 05 Sep 06:00 (your time)` (live, driven by
  `CronBox`'s `onLocal`, not gated on save).
- Blurred → `GET /api/settings` shows `backup_cron: "0 */6 * * *"`.
- Typed `bad`: helper → `invalid expression`; blurred → GET **unchanged**
  (`"0 */6 * * *"`), confirming the malformed value never reached
  `PATCH`/`configure_scheduler()`.
- Cleared the field: helper → `off`; blurred → GET shows `backup_cron: ""`.

**4. Preset menu, Telegram digest row** — pass, all sub-checks:
- Menu opens with exactly the 7 expected items, right-aligned mono
  expressions: `Hourly 0 * * * *`, `Every 6 hours 0 */6 * * *`,
  `Daily 03:00 0 3 * * *`, `Weekdays 09:00 0 9 * * mon-fri`,
  `Weekly Monday 08:00 0 8 * * mon`, `Monthly 1st 08:00 0 8 1 * *`, `Off`.
- No item ticked (`aria-selected="true"` count = 0) — correct, since
  `digest_cron` was `0 18 * * *`, which matches none of the presets.
- Screenshot: `v2-testing/artifacts/design/cron2.png` (clipped to the
  Scheduler section — the menu extends past that clip rect, which is a
  screenshot-crop artifact, not a real bug; a full-page shot,
  `cron2_full.png`, confirms the menu renders completely inside the 900px
  viewport, bottom edge at y=838, no clipping or z-index issue).
- Picked "Weekdays 09:00": field → `0 9 * * mon-fri`, helper →
  `weekdays at 09:00 UTC · next Mon 07 Sep 09:00 (your time)`, menu closed,
  `GET /api/settings` confirms `digest_cron: "0 9 * * mon-fri"`.
- Escape closes the menu (re-opened, confirmed open, pressed Escape,
  confirmed closed).
- Click outside the menu (top-left corner of the page) closes it too.

**5. Dark appearance screenshot** — pass. `v2-testing/artifacts/design/cron3.png`.
Helper tones (`--helper-ink` / `--muted`) stay legible against the dark
field/background tokens; field borders and the Preset trigger keep contrast.
Note: this shot was taken between steps 3-4 and step 6 (restore), so it
shows the DB-backup field cleared ("off") and the Telegram digest field
already switched to the Weekdays preset — that's just test sequencing, not
a defect; it also incidentally shows the same row correctly re-rendering
both an empty ("off") and a populated cron value in dark mode without
layout shift.

**6. Restore** — pass. All five values `PATCH`ed back; a final GET matches
the table above exactly.

## Manual next-run cross-check

For `0 9 * * mon-fri` picked in step 4, from the container's own clock
(2026-09-05T00:48 UTC, a Saturday): the next weekday-09:00 UTC slot is
**Monday 2026-09-07 09:00 UTC**. The UI's helper line read
`next Mon 07 Sep 09:00 (your time)` — matches exactly (container's browser
timezone is UTC, so "your time" == UTC here).

## Anything odd

Nothing found in the app itself. The only oddity was self-inflicted: the
first `cron2.png` capture used a screenshot clip sized to the Scheduler
section's own bounding box, which cut off the bottom of the open preset
menu since the menu overflows that box by design (it's positioned
`absolute`, layered above later rows). A full-page screenshot shows the
menu rendering completely and correctly. No misalignment, no clipped text,
no incorrect next-run date anywhere else.
