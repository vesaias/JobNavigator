# WCAG contrast ramp -- JobNavigator v2 skins

Repo `V:\JTrakProject`, branch `v2-redesign`, HEAD `b728e8c30fcea64c709485db0a45bad004e9da84`.

Source: `frontend/src/v2/theme.css`. Ratios computed with WCAG 2.x relative-luminance formula
(sRGB -> linearized -> `0.2126R + 0.7152G + 0.0722B`, `(L1+0.05)/(L2+0.05)`).
Text pairs: pass marks are AA normal (>=4.5:1) and AAA (>=7:1). Non-text pairs
(`--line`, `--line-strong`, `--edge`) use the UI/non-text AA threshold (>=3:1); `--line` is
reported for information only (it is a hairline divider, not a required-contrast boundary).
Chart invariants: `--series-new` on `--stage-applied` >=2:1, on `--bg` >=3:1.

## editorial -- light

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 17.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 7.66:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 3.44:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface` | 3.44:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--good` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--warn` | `--surface` | 5.38:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 6.81:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 15.29:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 6.73:1 | AA pass, AAA fail |  |
| `--muted` | `--surface-2` | 3.02:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 3.02:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 5.37:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 5.37:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 4.73:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 5.98:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 16.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 7.22:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 3.24:1 | AA FAIL, AAA fail |  |
| `--faint` | `--bg` | 3.24:1 | AA FAIL, AAA fail |  |
| `--accent` | `--bg` | 5.76:1 | AA pass, AAA fail |  |
| `--good` | `--bg` | 5.76:1 | AA pass, AAA fail |  |
| `--warn` | `--bg` | 5.07:1 | AA pass, AAA fail |  |
| `--bad` | `--bg` | 6.42:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 6.11:1 | AA pass, AAA fail | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 5.32:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 14.53:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 6.41:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 2.57:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 7.48:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.76:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.82:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.10:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 3.16:1 | pass (>= 3:1) |  |

## editorial -- dark

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 14.37:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 8.16:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 4.09:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface` | 4.09:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface` | 8.00:1 | AA pass, AAA pass |  |
| `--good` | `--surface` | 8.00:1 | AA pass, AAA pass |  |
| `--warn` | `--surface` | 7.42:1 | AA pass, AAA pass |  |
| `--bad` | `--surface` | 6.48:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 13.31:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 7.56:1 | AA pass, AAA pass |  |
| `--muted` | `--surface-2` | 3.79:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 3.79:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 7.41:1 | AA pass, AAA pass |  |
| `--good` | `--surface-2` | 7.41:1 | AA pass, AAA pass |  |
| `--warn` | `--surface-2` | 6.87:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 6.00:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 15.36:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 8.72:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 4.37:1 | AA FAIL, AAA fail |  |
| `--faint` | `--bg` | 4.37:1 | AA FAIL, AAA fail |  |
| `--accent` | `--bg` | 8.55:1 | AA pass, AAA pass |  |
| `--good` | `--bg` | 8.55:1 | AA pass, AAA pass |  |
| `--warn` | `--bg` | 7.93:1 | AA pass, AAA pass |  |
| `--bad` | `--bg` | 6.93:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 8.55:1 | AA pass, AAA pass | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 6.89:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 17.28:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 5.94:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 3.06:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 8.89:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.30:1 | info | informational |
| `--line-strong` | `--surface` | 1.83:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 4.01:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.20:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 4.38:1 | pass (>= 3:1) |  |

## tone3 -- light

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 17.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 7.66:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 3.88:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface` | 3.88:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--good` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--warn` | `--surface` | 5.38:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 6.81:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 15.43:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 6.79:1 | AA pass, AAA fail |  |
| `--muted` | `--surface-2` | 3.44:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 3.44:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 5.41:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 5.41:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 4.77:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 6.04:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 16.52:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 7.27:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 3.68:1 | AA FAIL, AAA fail |  |
| `--faint` | `--bg` | 3.68:1 | AA FAIL, AAA fail |  |
| `--accent` | `--bg` | 5.80:1 | AA pass, AAA fail |  |
| `--good` | `--bg` | 5.80:1 | AA pass, AAA fail |  |
| `--warn` | `--bg` | 5.11:1 | AA pass, AAA fail |  |
| `--bad` | `--bg` | 6.46:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 6.11:1 | AA pass, AAA fail | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 5.32:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 14.53:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 6.41:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 3.03:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 7.48:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.76:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.82:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.10:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 3.18:1 | pass (>= 3:1) |  |

## tone3 -- dark

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 13.39:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 8.44:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 4.58:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 4.58:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 7.82:1 | AA pass, AAA pass |  |
| `--good` | `--surface` | 7.82:1 | AA pass, AAA pass |  |
| `--warn` | `--surface` | 7.25:1 | AA pass, AAA pass |  |
| `--bad` | `--surface` | 6.33:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 12.20:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 7.69:1 | AA pass, AAA pass |  |
| `--muted` | `--surface-2` | 4.18:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 4.18:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 7.12:1 | AA pass, AAA pass |  |
| `--good` | `--surface-2` | 7.12:1 | AA pass, AAA pass |  |
| `--warn` | `--surface-2` | 6.61:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 5.77:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 14.39:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 9.07:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 4.93:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 4.93:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 8.40:1 | AA pass, AAA pass |  |
| `--good` | `--bg` | 8.40:1 | AA pass, AAA pass |  |
| `--warn` | `--bg` | 7.79:1 | AA pass, AAA pass |  |
| `--bad` | `--bg` | 6.80:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 8.55:1 | AA pass, AAA pass | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 6.80:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 17.28:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 5.94:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 3.50:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 8.89:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.33:1 | info | informational |
| `--line-strong` | `--surface` | 1.78:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.91:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.20:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 4.30:1 | pass (>= 3:1) |  |

## tone2 -- light

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 17.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 7.66:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 4.33:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface` | 4.33:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--good` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--warn` | `--surface` | 5.38:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 6.81:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 15.55:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 6.84:1 | AA pass, AAA fail |  |
| `--muted` | `--surface-2` | 3.86:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 3.86:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 5.46:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 5.46:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 4.81:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 6.08:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 16.56:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 7.28:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 4.12:1 | AA FAIL, AAA fail |  |
| `--faint` | `--bg` | 4.12:1 | AA FAIL, AAA fail |  |
| `--accent` | `--bg` | 5.81:1 | AA pass, AAA fail |  |
| `--good` | `--bg` | 5.81:1 | AA pass, AAA fail |  |
| `--warn` | `--bg` | 5.12:1 | AA pass, AAA fail |  |
| `--bad` | `--bg` | 6.48:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 6.11:1 | AA pass, AAA fail | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 5.32:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 14.53:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 6.41:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 3.57:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 7.48:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.76:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.82:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.10:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 3.19:1 | pass (>= 3:1) |  |

## tone2 -- dark

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 12.37:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 8.61:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 5.06:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 5.06:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 7.56:1 | AA pass, AAA pass |  |
| `--good` | `--surface` | 7.56:1 | AA pass, AAA pass |  |
| `--warn` | `--surface` | 7.01:1 | AA pass, AAA pass |  |
| `--bad` | `--surface` | 6.12:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 11.22:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 7.81:1 | AA pass, AAA pass |  |
| `--muted` | `--surface-2` | 4.59:1 | AA pass, AAA fail |  |
| `--faint` | `--surface-2` | 4.59:1 | AA pass, AAA fail |  |
| `--accent` | `--surface-2` | 6.86:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 6.86:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 6.36:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 5.55:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 13.49:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 9.39:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 5.52:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 5.52:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 8.25:1 | AA pass, AAA pass |  |
| `--good` | `--bg` | 8.25:1 | AA pass, AAA pass |  |
| `--warn` | `--bg` | 7.65:1 | AA pass, AAA pass |  |
| `--bad` | `--bg` | 6.68:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 8.55:1 | AA pass, AAA pass | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 6.64:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 17.28:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 5.94:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 3.95:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 8.89:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.33:1 | info | informational |
| `--line-strong` | `--surface` | 1.73:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.79:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.20:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 4.22:1 | pass (>= 3:1) |  |

## tone1 -- light

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 17.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 7.66:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 4.91:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 4.91:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--good` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--warn` | `--surface` | 5.38:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 6.81:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 15.68:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 6.90:1 | AA pass, AAA fail |  |
| `--muted` | `--surface-2` | 4.42:1 | AA FAIL, AAA fail |  |
| `--faint` | `--surface-2` | 4.42:1 | AA FAIL, AAA fail |  |
| `--accent` | `--surface-2` | 5.50:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 5.50:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 4.85:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 6.14:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 16.67:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 7.33:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 4.70:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 4.70:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 5.85:1 | AA pass, AAA fail |  |
| `--good` | `--bg` | 5.85:1 | AA pass, AAA fail |  |
| `--warn` | `--bg` | 5.15:1 | AA pass, AAA fail |  |
| `--bad` | `--bg` | 6.52:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 6.11:1 | AA pass, AAA fail | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 5.32:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 14.53:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 6.41:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 4.16:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 7.48:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.76:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.82:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.10:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 3.21:1 | pass (>= 3:1) |  |

## tone1 -- dark

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 11.56:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 8.93:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 5.66:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 5.66:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 7.37:1 | AA pass, AAA pass |  |
| `--good` | `--surface` | 7.37:1 | AA pass, AAA pass |  |
| `--warn` | `--surface` | 6.83:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 5.96:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 10.20:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 7.88:1 | AA pass, AAA pass |  |
| `--muted` | `--surface-2` | 5.00:1 | AA pass, AAA fail |  |
| `--faint` | `--surface-2` | 5.00:1 | AA pass, AAA fail |  |
| `--accent` | `--surface-2` | 6.50:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 6.50:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 6.03:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 5.26:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 12.65:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 9.78:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 6.20:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 6.20:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 8.06:1 | AA pass, AAA pass |  |
| `--good` | `--bg` | 8.06:1 | AA pass, AAA pass |  |
| `--warn` | `--bg` | 7.48:1 | AA pass, AAA pass |  |
| `--bad` | `--bg` | 6.53:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 8.55:1 | AA pass, AAA pass | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 6.53:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 17.28:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 5.94:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 4.49:1 | AA FAIL, AAA fail |  |
| `--rail-accent` | `--rail` | 8.89:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.68:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.69:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.20:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 4.13:1 | pass (>= 3:1) |  |

## default -- light

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 17.41:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 7.66:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 5.52:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 5.52:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--good` | `--surface` | 6.11:1 | AA pass, AAA fail |  |
| `--warn` | `--surface` | 5.38:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 6.81:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 15.83:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 6.96:1 | AA pass, AAA fail |  |
| `--muted` | `--surface-2` | 5.02:1 | AA pass, AAA fail |  |
| `--faint` | `--surface-2` | 5.02:1 | AA pass, AAA fail |  |
| `--accent` | `--surface-2` | 5.56:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 5.56:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 4.89:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 6.20:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 16.82:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 7.40:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 5.33:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 5.33:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 5.90:1 | AA pass, AAA fail |  |
| `--good` | `--bg` | 5.90:1 | AA pass, AAA fail |  |
| `--warn` | `--bg` | 5.20:1 | AA pass, AAA fail |  |
| `--bad` | `--bg` | 6.58:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 6.11:1 | AA pass, AAA fail | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 5.32:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 14.53:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 6.41:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 4.88:1 | AA pass, AAA fail |  |
| `--rail-accent` | `--rail` | 7.48:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.36:1 | info | informational |
| `--line-strong` | `--surface` | 1.76:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.82:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.10:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 3.24:1 | pass (>= 3:1) |  |

## default -- dark

| Foreground | Background | Ratio | Result | Note |
|---|---|---|---|---|
| `--text` | `--surface` | 10.64:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface` | 9.09:1 | AA pass, AAA pass |  |
| `--muted` | `--surface` | 6.17:1 | AA pass, AAA fail |  |
| `--faint` | `--surface` | 6.17:1 | AA pass, AAA fail |  |
| `--accent` | `--surface` | 7.11:1 | AA pass, AAA pass |  |
| `--good` | `--surface` | 7.11:1 | AA pass, AAA pass |  |
| `--warn` | `--surface` | 6.59:1 | AA pass, AAA fail |  |
| `--bad` | `--surface` | 5.75:1 | AA pass, AAA fail |  |
| `--text` | `--surface-2` | 9.30:1 | AA pass, AAA pass |  |
| `--text-2` | `--surface-2` | 7.95:1 | AA pass, AAA pass |  |
| `--muted` | `--surface-2` | 5.40:1 | AA pass, AAA fail |  |
| `--faint` | `--surface-2` | 5.40:1 | AA pass, AAA fail |  |
| `--accent` | `--surface-2` | 6.21:1 | AA pass, AAA fail |  |
| `--good` | `--surface-2` | 6.21:1 | AA pass, AAA fail |  |
| `--warn` | `--surface-2` | 5.76:1 | AA pass, AAA fail |  |
| `--bad` | `--surface-2` | 5.03:1 | AA pass, AAA fail |  |
| `--text` | `--bg` | 11.82:1 | AA pass, AAA pass |  |
| `--text-2` | `--bg` | 10.10:1 | AA pass, AAA pass |  |
| `--muted` | `--bg` | 6.86:1 | AA pass, AAA fail |  |
| `--faint` | `--bg` | 6.86:1 | AA pass, AAA fail |  |
| `--accent` | `--bg` | 7.90:1 | AA pass, AAA pass |  |
| `--good` | `--bg` | 7.90:1 | AA pass, AAA pass |  |
| `--warn` | `--bg` | 7.32:1 | AA pass, AAA pass |  |
| `--bad` | `--bg` | 6.39:1 | AA pass, AAA fail |  |
| `--accent-ink` | `--accent` | 8.55:1 | AA pass, AAA pass | primary button |
| `--pill-on-ink (=--accent)` | `--accent-soft` | 6.37:1 | AA pass, AAA fail | selected pill / accent wash |
| `--rail-ink` | `--rail` | 17.28:1 | AA pass, AAA pass |  |
| `--rail-text` | `--rail` | 5.94:1 | AA pass, AAA fail |  |
| `--rail-dim` | `--rail` | 5.08:1 | AA pass, AAA fail |  |
| `--rail-accent` | `--rail` | 8.89:1 | AA pass, AAA pass |  |
| `--line` | `--surface` | 1.37:1 | info | informational |
| `--line-strong` | `--surface` | 1.62:1 | FAIL | pass >=3:1 |
| `--edge` | `--surface` | 3.56:1 | pass | pass >=3:1 |
| `--series-new` | `--stage-applied` | 2.20:1 | pass (>= 2:1) |  |
| `--series-new` | `--bg` | 4.04:1 | pass (>= 3:1) |  |

## Summary

| Skin | Mode | Min text ratio | AA text fails | Failing pairs |
|---|---|---|---|---|
| editorial | light | 2.57:1 | 7 | --muted on --surface (3.44:1); --faint on --surface (3.44:1); --muted on --surface-2 (3.02:1); --faint on --surface-2 (3.02:1); --muted on --bg (3.24:1); --faint on --bg (3.24:1); --rail-dim on --rail (2.57:1) |
| editorial | dark | 3.06:1 | 7 | --muted on --surface (4.09:1); --faint on --surface (4.09:1); --muted on --surface-2 (3.79:1); --faint on --surface-2 (3.79:1); --muted on --bg (4.37:1); --faint on --bg (4.37:1); --rail-dim on --rail (3.06:1) |
| tone3 | light | 3.03:1 | 7 | --muted on --surface (3.88:1); --faint on --surface (3.88:1); --muted on --surface-2 (3.44:1); --faint on --surface-2 (3.44:1); --muted on --bg (3.68:1); --faint on --bg (3.68:1); --rail-dim on --rail (3.03:1) |
| tone3 | dark | 3.50:1 | 3 | --muted on --surface-2 (4.18:1); --faint on --surface-2 (4.18:1); --rail-dim on --rail (3.50:1) |
| tone2 | light | 3.57:1 | 7 | --muted on --surface (4.33:1); --faint on --surface (4.33:1); --muted on --surface-2 (3.86:1); --faint on --surface-2 (3.86:1); --muted on --bg (4.12:1); --faint on --bg (4.12:1); --rail-dim on --rail (3.57:1) |
| tone2 | dark | 3.95:1 | 1 | --rail-dim on --rail (3.95:1) |
| tone1 | light | 4.16:1 | 3 | --muted on --surface-2 (4.42:1); --faint on --surface-2 (4.42:1); --rail-dim on --rail (4.16:1) |
| tone1 | dark | 4.49:1 | 1 | --rail-dim on --rail (4.49:1) |
| default | light | 4.88:1 | 0 | none |
| default | dark | 5.03:1 | 0 | none |

## Reading the ramp

Only two tokens ever fail AA on the ramp -- `--muted` (and its `--faint` alias, always `var(--muted)`) and `--rail-dim` -- and both get progressively darker relative to their grounds as the skin moves `default` -> `tone1` -> `tone2` -> `tone3` -> `editorial`. `--rail-dim` on `--rail` is the first casualty: it clears AA at `default` in both modes but fails from `tone1` on in both modes too (light 4.16:1, dark 4.49:1) and keeps sliding to 2.57:1 light / 3.06:1 dark at `editorial`. `--muted` degrades on a slower, mode-asymmetric schedule -- in light it is already failing at `tone1` (but only on `--surface-2`, 4.42:1), fails on all three grounds by `tone2` (3.86-4.33:1) and bottoms out at `editorial` (3.02-3.44:1); in dark it holds AA through `tone2` entirely (only `--rail-dim` fails there) and first slips at `tone3`, and only on `--surface-2` (4.18:1), reaching `editorial` dark at a comparatively gentler 3.79-4.37:1 versus editorial light's 3.02-3.44:1. So light degrades earlier and lands harder; dark degrades later and lands softer. Nothing else moves: `--text`, `--text-2`, `--accent`/`--good`, `--warn`, `--bad`, the rail's `--rail-ink`/`--rail-text`/`--rail-accent`, the primary button (`--accent-ink` on `--accent`) and the selected-pill wash all stay comfortably AA (most AAA) at every step, because the ramp's light-mode delta is only four tokens (`--bg`, `--surface-2`, `--muted`, `--rail-dim`) and none of those other tokens is one of them. `--line-strong` on `--surface` never passes the >=3:1 non-text threshold anywhere on the ramp (1.62:1 default dark to 1.83:1 editorial dark, a flat 1.76:1 across every light skin) -- `--line-strong` itself is byte-identical the whole way, so the small drift is only `--surface` moving underneath it, and the pair was never designed to carry its own contrast (it is a hairline, not a control boundary). `--edge` on `--surface` and the two `--series-new` chart-invariant pairs are likewise untouched by the ramp in absolute hue and stay well clear of their floors (`--edge` 3.56-4.01:1, `--series-new`/`--stage-applied` a flat ~2.10:1 light / 2.20:1 dark, `--series-new`/`--bg` 3.16-4.38:1) at every skin and mode.
