# ADR 0005 — Bar display and panel UX

- **Status**: Accepted (2026-09-08); amended 2026-09-08 (refresh cadence + reset clock)

## Context

Bar space is the scarcest resource (user decision: "越窄越好"); the panel is
where detail belongs. copilot-companion's interaction grammar is the community
baseline users already know.

## Decision

### Bar glyph

- **Glyph (default ⚡/GLM mark) + single percentage**, default = **5-hour
  window** usage.
- `barDisplay` widget setting (via `omarchy bar set`): `percent` (5 h, default)
  · `weekly` · `both` · `icon`.
- Middle-click cycles `barDisplay`; right-click forces refresh.
- Glyph/number color shifts toward the theme's urgent color as the displayed
  window fills (visible without opening anything).

### Panel

```
┌ Zhipu Coding Plan — PRO · cn · live ──────────┐
│ 5h window      ▓▓▓▓▓▓░░░░  63%   resets 1h 12m│
│ Weekly         ▓▓▓░░░░░░░  34%   resets 4d    │
│ MCP monthly    ▓▓▓▓▓▓▓░░░  71%   resets 12d   │
│   search-prime 420 · web-reader 88 · zread 31 │
├ Models (this cycle) ──────────────────────────┤
│ GLM-5.1        ▓▓▓▓▓▓▓░  12.4k tok · 89 req   │
│ GLM-5-Code     ▓▓░░░░░░   3.1k tok · 21 req   │
│ …hover: input/output/reasoning/cached split   │
├───────────────────────────────────────────────┤
│ fetched 12s ago · j/k scroll · r refresh · b web · Esc ⏎ │
└───────────────────────────────────────────────┘
```

- Header: plan level badge, region, live/stale indicator.
- Weekly meter renders "—" when the plan has no weekly quota (ADR 0003);
  absent windows are named in a "Not reported on this plan" line instead of
  showing zero meters.
- Staleness: on refresh failure keep last record + show age and error line.
- Model section is **last-24h** (windowed endpoint, ADR-0003 amendment), plus
  24h stat tiles (requests, tokens, web search, web read).
- Keys: `j`/`k` scroll · `r` refresh · `b` open region usage page
  (bigmodel.cn / z.ai usage stats) · `Esc` close · `Tab` neighbor panel.

### Widget settings (via `omarchy bar set`, stored in `shell.json`)

| Key | Default | Meaning |
| --- | --- | --- |
| `refreshIntervalSec` | `300` | collector cadence |
| `barDisplay` | `"percent"` | bar label mode |
| `glyph` | ⚡ | override if font lacks default |

### IPC (target `zhipu`; exact registration verified against shell source during implementation)

```
omarchy-shell zhipu open|close|toggle|refresh|usage
```

## Consequences

- Bar footprint ≈ glyph + 3–4 characters; `both` mode is the widest opt-in.
- Panel stays a dumb renderer; every number comes from the state record.
- All theming via Omarchy `Style` tokens — no hardcoded colors.

## Amendment (2026-09-08, refresh cadence + reset clock)

- **`refreshIntervalSec` default 300 → 120.** Instrumented verification
  showed the timer/process chain healthy end-to-end, but 5-minute cadence
  reads as "never refreshes" in practice, and the first fetch after a shell
  restart can take ~100 s (cold DNS/TLS) before the first record lands.
  120 s keeps three GETs per cycle polite while feeling live. The interval
  binding also gained a weather-style `parseInt(...) || fallback` guard:
  widget `settings` arrive empty and fill asynchronously, and a NaN interval
  would silently kill the Timer.
- **Absolute reset time.** Meter captions and the bar tooltip now show both
  the countdown ("resets in 2h 5m") and the wall-clock rollover ("21:16", or
  "9/13 08:22" when it crosses midnight) — both derived from the existing
  `nextResetTime` in the quota payload. No new endpoint needed.
- **Subscription renewal date (套餐续费时间): investigated, not available
  via key.** `/api/coding/user/*`, `/api/paas/v4/user/*` and friends return
  404/gateway-404 with API-key auth on open.bigmodel.cn; the official docs
  place subscription management behind the web console (套餐概览, session
  cookies). A login/session flow was considered and rejected for now:
  cookie storage inside a bar plugin is a fragile, high-risk surface for a
  date the user checks monthly. Revisit only with real demand.

## Amendment (2026-09-08, bar face layout)

The bolt glyph (\uf0e7) paints 13 px of ink inside a 9-unit advance box, and
`WidgetButton` pads its text with ~8.5 units of left margin — concatenated
"glyph + label" therefore rendered a ~27 px visual gap that no space-character
choice could shrink (single/thin/no-space all measured identical). The face
is now drawn as two siblings: the glyph `Text` at the slot origin and the
`WidgetButton` slid under the glyph's advance box
(`x: glyphAdv - Style.space(8)`), putting the two inks ~4 px apart while the
whole face stays inside the clickable slot (a face-wide `MouseArea` owns
interaction; the button keeps painting). `openPanelIndicatorWidth` reports
the root's implicit width so the open-panel mark spans exactly the painted
face instead of the 55%-of-slot default.
