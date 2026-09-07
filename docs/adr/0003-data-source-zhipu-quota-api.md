# ADR 0003 — Data source: Zhipu monitor quota API

- **Status**: Accepted (2026-09-08); amended 2026-09-08 after live verification

## Context

Zhipu exposes (unofficial, undocumented-but-stable-in-practice) monitor
endpoints used by the official web dashboards. Verified against multiple
independent implementations (OpenUsage, `cc-switch` usage templates,
`zai-quota`, `opencodex` quota provider). Both regions are supported and the
two keys are **not interchangeable**.

## Decision

### Endpoints

| Purpose | Path (appended to region base) |
| --- | --- |
| Quotas + plan level | `GET /api/monitor/usage/quota/limit` |
| Per-model stats | `GET /api/monitor/usage/model-usage` |

| Region | Base | Default |
| --- | --- | --- |
| `cn` | `https://open.bigmodel.cn` | **yes** |
| `intl` | `https://api.z.ai` | no |

Auth header: `Authorization: Bearer <key>`; on 401 retry with the raw key
(sources disagree — one header probe handles both).

Team plans: optional config fields `organization` / `project` are sent as
`bigmodel-organization` / `bigmodel-project` headers (observed on the
bigmodel.cn team usage page).

### Parsing rules for `quota/limit`

From `data`:

- `level` → plan tier (`lite` / `standard` / `pro` / `max`).
- `limits[]` rows, in precedence order:
  - `TOKENS_LIMIT` / `CREDIT_LIMIT` rows: sort by `nextResetTime` ascending →
    **[0] = 5-hour window, [1] = weekly window** (old plans have only one row →
    no weekly meter). Newer protocol rows carry `unit`/`number` discriminators
    (`unit 3, number 5` → 5 h; `unit 6, number 1` → weekly) — used when
    present, `nextResetTime` sort otherwise.
  - `TIME_LIMIT` row → **MCP monthly budget**; `usageDetails[]` carries
    per-tool usage (search-prime / web-reader / zread).
- Percentage: use `percentage` when present, else `currentValue / usage * 100`.
- `nextResetTime`: epoch value — normalize ms-vs-s (> 1e12 ⇒ ms).
- **Legacy fallback**: only when `limits` is entirely absent, fall back to
  legacy flat fields (`fiveHourPercent`, `weeklyPercent`, `monthlyMCPUsage`).
  Present-but-empty `limits` must **not** produce a legacy render.

### Per-model stats

`model-usage` rows (`data[]`): model name, request count, input / output /
reasoning / cached tokens. Cost figures are **reference-only** on coding plans
(flat-fee billing) and are displayed as secondary detail, never as money owed.

## Consequences

- One primary call + two secondary calls per refresh; all plain GETs.
- The endpoints are unofficial and may change without notice — the collector
  must fail soft (keep last record, surface an error line in the panel).
- Weekly meter absence is a *state* ("no weekly quota on this plan"), distinct
  from 0%.

## Amendment (2026-09-08, live verification)

Captured live against `open.bigmodel.cn` (pro plan, new protocol):

- **Auth**: raw `Authorization: <key>` accepted (Bearer kept as 401 fallback).
- **`percentage` floors to an integer** (1.525 % → 1). When
  `currentValue`/`usage` exist, the collector **recomputes** the percentage
  for display precision; the API value is only the fallback.
- **model-usage / tool-usage are windowed endpoints** (`startTime`/`endTime`
  query params, `YYYY-MM-DD HH:MM:SS`). They are queried for the **last 24
  hours**, not the billing cycle: `modelSummaryList[].{modelName,totalTokens}`
  and `totalUsage.{totalModelCallCount,totalNetworkSearchCount,
  totalWebReadMcpCount,totalZreadMcpCount}`. The panel labels the section
  "Models · last 24h" accordingly.
- The new (credit-based) protocol reports **no `TIME_LIMIT` row**; the panel
  then names the absence instead of showing a zero meter, and the 24h tool
  counts from tool-usage stay visible.
