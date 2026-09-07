# ADR 0001 — Plugin identity and scope

- **Status**: Accepted (2026-09-08)
- **Deciders**: Aniakea (project owner), via grill-with-docs interview

## Context

We need a new Omarchy (Quattro shell) menu-bar plugin that surfaces Zhipu GLM
Coding Plan usage. The reference design is
[`io.github.ramous19.copilot-companion`](https://github.com/ramous19/omarchy-copilot-companion);
the development contract follows
<https://plugins.omarchy.org/develop.html>.

The plugin ID must be permanently namespaced for marketplace publication.
The local GitHub identity is `Aniakea` (verified via `gh api user`).

## Decision

| Field | Value |
| --- | --- |
| Plugin ID | `io.github.aniakea.zhipu-coding-usage` |
| Project / repo name | `zhipu-coding-usage` (repo: `github.com/Aniakea/zhipu-coding-usage`) |
| Display name | **Zhipu Coding Usage** |
| Plugin kind | `bar-widget` (single kind; details panel is nested, not a separate `panel` kind) |
| UI language | English |
| Default bar section | right |

**Scope — all three usage windows, not two:**

1. **5-hour rolling window** (`TOKENS_LIMIT`, shortest `nextResetTime`)
2. **Weekly window** (`TOKENS_LIMIT`, second shortest `nextResetTime`)
3. **MCP monthly budget** (`TIME_LIMIT`; per-tool details: search-prime / web-reader / zread)

Plus: plan level badge (lite / standard / pro / max), reset countdowns,
per-model usage breakdown (from `model-usage` endpoint), and threshold desktop
notifications (ADR 0006).

## Consequences

- The plugin answers "can I still burn quota right now" (5h), "am I safe this
  week" (weekly), and "how much MCP tooling is left this month" in one panel.
- Old plans with a single `TOKENS_LIMIT` render the weekly meter as absent
  (not zero) — see ADR 0003 parsing rules.
- The name `zhipu-coding-usage` (not `glm-usage`) matches Zhipu's official
  "Coding Plan" branding for the primarily-CN audience, while keeping the
  `io.github.*` marketplace convention.

## Amendment (2026-09-08, scope reduction)

The **MCP monthly budget (`TIME_LIMIT`) is removed** from scope by owner
decision: the parser ignores those rows, the panel no longer renders an MCP
meter or per-tool line, and the 75/90/100 % notification rule for it is gone
(ADR 0006). The 24 h web-search / web-read counts from the tool-usage
endpoint are unrelated to that budget and stay.

## Second amendment (2026-09-08, reset-card display dropped)

**Quota reset cards (用量重置卡) are out of scope by owner decision.**
Investigated: cards are consumable 5-hour/weekly resets with per-card
expiry, granted via ZCode off-peak rules or events — but their count and
type are only exposed through the ZCode/account-login channel. Eighteen
endpoint probes against the key-authenticated namespaces returned 404, the
`quota/limit` payload carries no card fields, and no community tool reads
them with an API key. Options (packet capture, manual config, login-flow
integration) were offered and declined.
