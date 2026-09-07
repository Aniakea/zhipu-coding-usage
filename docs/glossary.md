# Glossary — zhipu-coding-usage

Terms used across the ADRs and codebase. Keep entries short; link the ADR that
decides usage.

## Omarchy / shell

- **Omarchy** — Arch-based Linux desktop distribution; ships the Quattro shell.
- **Quattro / omarchy-shell** — The Quickshell-based bar/shell process that hosts plugins. Plugins **share this long-running unsandboxed process**.
- **Quickshell** — Qt/QML framework Omarchy's shell is built on.
- **Plugin** — a folder under `~/.config/omarchy/plugins/<id>/` with a `manifest.json` and QML entry points.
- **`bar-widget`** — plugin kind rendered as an item in the active bar (`entryPoints.barWidget: "BarWidget.qml"`). Details panels are nested inside it (not a separate `panel` kind).
- **Plugin ID** — permanent namespaced id, e.g. `io.github.aniakea.zhipu-coding-usage`. `omarchy.*` is reserved; no symlinks allowed in plugin folders.
- **`omarchy plugin clone … --edit`** — scaffolds a local editable copy of a built-in plugin; keep the printed clone ID while developing.
- **`omarchy plugin validate` / `qmllint -I "$OMARCHY_PATH/shell"`** — manifest and QML validation gates.
- **`omarchy bar set <id> <key> <value> [--json]`** — per-widget settings stored in `~/.config/omarchy/shell.json` (numbers need `--json`).
- **`omarchy-shell <target> <command>`** — IPC route into a plugin's exposed functions (e.g. `open`, `refresh`).
- **Widget settings** — `refreshIntervalSec`, `barDisplay`, `glyph` (ADR 0005).

## Zhipu / GLM Coding Plan

- **Zhipu Coding Plan / GLM Coding Plan** — flat-fee subscription ("套餐") covering GLM coding models; tiers `lite` / `standard` / `pro` / `max` = **level** in the API.
- **Regions** — `cn` = `open.bigmodel.cn` (default), `intl` = `api.z.ai`. Keys are **not interchangeable** between regions (ADR 0003).
- **Quota API** — `GET {base}/api/monitor/usage/quota/limit` (unofficial, dashboard-grade).
- **`TOKENS_LIMIT`** — a token-window limit row. New plans return **two** (5 h + weekly); old plans one. Identified as [0]=5 h, [1]=weekly by `nextResetTime` ascending, or by `unit`/`number` discriminators (`unit 3 num 5` → 5 h, `unit 6 num 1` → weekly).
- **`CREDIT_LIMIT`** — newer-protocol row type serving the same two windows.
- **`TIME_LIMIT`** — MCP monthly tool budget row; `usageDetails[]` = per-tool usage (search-prime / web-reader / zread).
- **5-hour window** — rolling quota window; resets ~every 5 h.
- **Weekly window** — weekly quota; absent on old plans (render "—", not 0%).
- **MCP monthly** — 30-day budget for MCP tools (web search / reader / zread), counted in tool calls.
- **`nextResetTime`** — epoch when the window resets (ms if > 1e12 else s); doubles as cycle identity for notification dedup (ADR 0006).
- **`percentage` / `currentValue` / `usage`** — used-percent; computed as `currentValue / usage * 100` when `percentage` is absent.
- **Model-usage API** — `GET {base}/api/monitor/usage/model-usage` with `startTime`/`endTime` (`YYYY-MM-DD HH:MM:SS`); queried for the **last 24 hours**. Returns hourly series (`x_time`, `modelCallCount`, `tokensUsage`) plus `totalUsage.modelSummaryList[].{modelName,totalTokens,sortOrder}`; the panel's model ranking uses the summary list. Per-model request counts are not published.
- **Legacy payload** — pre-`limits` flat fields (`fiveHourPercent`, `weeklyPercent`, `monthlyMCPUsage`); used **only** when `limits` is absent entirely.

## This plugin's architecture

- **Collector** — `bin/zhipu-coding-usage` (entry) + `bin/zhipu_collector.py` (fetch/parse), Python 3 stdlib-only; the only component that holds the key and talks to the network (ADR 0002, 0004).
- **State record** — `~/.local/state/omarchy/zhipu/usage.json`, atomically written; the panel renders it verbatim. On fetch failure the collector **merges**: last good windows are kept, `error` is stamped, header shows "stale".
- **Notify state** — `~/.local/state/omarchy/zhipu/notify-state.json`; once-per-level-per-cycle dedup keyed by window + threshold + `nextResetTime` (ADR 0006).
- **Config file** — `~/.config/omarchy/zhipu-coding-usage.json` (`apiKey`, `region`, `notify`, `organization`, `project`).
- **Key lookup order** — env `ZHIPUAI_API_KEY` → `ZAI_API_KEY` → `GLM_API_KEY` → config file → opencode `auth.json` (ADR 0004, amended).
- **Live / stale** — panel indicator: "live" = fresh successful fetch; "stale" = rendering last good record after a failure, with age shown.
- **tool-usage** — windowed like model-usage (24 h); totals under `totalUsage`: `totalNetworkSearchCount` / `totalWebReadMcpCount` / `totalZreadMcpCount`, with per-tool detail in `toolDetails[].{modelName,totalUsageCount}`.
