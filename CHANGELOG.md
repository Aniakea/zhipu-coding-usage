# Changelog

## 0.3.0 - 2026-09-08

- Token charts: 24 h hourly line with peak-hour marking, plus day/week/month
  consumption lines accumulated in a local SQLite history
  (`~/.local/state/omarchy/zhipu/history.db`, 400-day retention).
- Pace projection for the weekly quota ("on this pace: exhausts Wed 14:00"),
  gated by a 2 h cycle floor and an outlasts-reset cutoff.
- Peak/off-peak badge (Mon–Fri 14:00–18:00 local = 3×) and off-peak share
  of the 24 h consumption.
- Predictive notification ~6 h before the projected 90 % crossing,
  deduped per weekly cycle; bilingual (en/zh) notifications.
- Panel i18n: `language` setting (`auto`/`en`/`zh`) with per-language
  formatters.
- CI: pytest + ruff + basedpyright, qmllint syntax smoke test.
- Entry split: notifications moved to `zhipu_notify` (278 → 140 pure LOC).

## 0.2.0 - 2026-09-08

- Removed the MCP monthly (`TIME_LIMIT`) pipeline end to end: meter, parser
  branch, notification rule, and legacy field mapping. The 24 h web-search /
  web-read counts are unrelated and stay.
- Recorded the reset-card display investigation as dropped (ADR-0001).

## 0.1.4 - 2026-09-08

- Manifest version tracking aligned with release tags; summary mentions
  reset countdowns.

## 0.1.3 - 2026-09-08

- Preview refresh and README fixes: embedded screenshot, Python 3.10+
  requirement, full collector path in key-setup examples.

## 0.1.2 - 2026-09-08

- Restored standard bar slot spacing (the ink-tight width had amputated the
  WidgetButton side margins); open-panel mark length decoupled from slot
  width and set to the painted ink face.

## 0.1.1 - 2026-09-08

- Key handling decoupled from OpenCode: runtime resolution is env → own
  config only; one-time `--set-key` / `--import-key` setup commands.
- Auto-refresh hardening: NaN-guarded interval, default 300 → 120 s.
- Absolute reset times in meters and tooltips.

## 0.1.0 - 2026-09-07

- Initial release: 5-hour and weekly quota meters with reset countdowns,
  per-model 24 h usage, threshold notifications, collector → JSON → QML
  architecture, dual-region (bigmodel.cn / api.z.ai) support.
