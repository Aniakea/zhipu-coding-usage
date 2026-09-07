# ADR 0002 — Architecture: collector → JSON state file → QML panel

- **Status**: Accepted (2026-09-08)

## Context

Three viable architectures for an Omarchy bar-widget that needs network data:

1. **Collector → JSON → QML** (the `copilot-companion` pattern): an external
   script periodically fetches/aggregates and writes one JSON record to
   `~/.local/state/omarchy/…`; the QML panel watches the file and renders
   whatever it says.
2. **Pure QML polling**: `XMLHttpRequest` inside the shell process.
3. **`service` + `bar-widget` kinds**: headless `Service.qml` singleton doing
   network I/O in-process.

## Decision

**Option 1 — collector → JSON → QML.**

- Collector: `bin/zhipu-coding-usage`, **Python 3, standard library only**
  (`urllib`, `json`, no pip dependencies — matches Arch's stock `python`).
- State file: `~/.local/state/omarchy/zhipu/usage.json`, written **atomically**
  (temp file + rename) so the panel never sees a partial record.
- QML side (`BarWidget.qml` + `Panel.qml`) is a **pure renderer**: it owns no
  arithmetic, no HTTP, no parsing — it draws what the record says.
- Panel triggers a refresh via IPC (`omarchy-shell zhipu refresh`) and on the
  widget's `refreshIntervalSec` timer (default 300 s, configurable through
  `omarchy bar set`).

## Consequences

- **Key isolation**: the API key never enters the long-running shell process
  or any QML/`shell.json` config the shell reads.
- **Testability**: the collector runs standalone (`--print`) and can be tested
  against fixture JSON without a bar.
- **Offline degrade**: on network failure the panel keeps rendering the last
  good record with a visible staleness marker, instead of blanking.
- **Cost**: requires `python3` on the host (guaranteed on Arch/Omarchy) and a
  state directory that must survive plugin removal semantics documented in the
  README (same as copilot-companion's `~/.local/state/omarchy/copilot/`).
- Collector is single-account in v1. Multi-account tiles (e.g. both a z.ai and
  a bigmodel.cn key) are future work.
