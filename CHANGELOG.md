# Changelog

## 1.0.3 - 2026-09-11

- Fixed threshold notifications so every level (75/90/100 %) fires once per
  cycle — the dedup identity previously omitted the threshold, letting the
  75 % alert permanently silence 90 % and 100 % in the same week.
- Fixed the stale merge: consecutive fetch failures now keep the last good
  windows on screen (the second failure previously blanked the panel).
- History failures no longer crash the collector: a corrupt or locked
  history.db degrades the charts to empty instead of killing the quota
  display; a refused state write exits cleanly with a plain message.
- HTTP redirects are refused (fail-closed): urllib would otherwise forward
  the Authorization header to whatever host a redirect names.
- `--set-key` is prompt-only — the key can no longer appear in the
  world-readable process command line.
- history.db is created mode 0600 (usage statistics stay user-only).
- Release packaging copies `bin/*` and smoke-imports every module from the
  assembled package — the v1.0.2 archives shipped without zhipu_secure.py
  and could not start; this can no longer pass green.
- ADR drift corrected (0002 entry point/interval, 0004 exit and prompt
  behavior, 0006 per-threshold identity).

## 1.0.2 - 2026-09-10

- Fail-closed local IO boundaries (marketplace security review follow-up,
  ADR-0010): config/credential/state reads go through O_NOFOLLOW +
  descriptor type/owner/mode checks + a 1 MiB cap (O_NONBLOCK also closes
  a FIFO hang); atomic writes hold a verified parent dir_fd for the temp
  file and rename; notify-send resolves from a root-owned absolute-path
  allowlist instead of the inherited PATH.

## 1.0.1 - 2026-09-08

- Fixed a doubled `%` in threshold notification titles (the value already
  carried the sign the template adds), and translated the window labels in
  Chinese notifications (they were English inside zh strings).

## 1.0.0 - 2026-09-08

- Stable release. Feature baseline: 5-hour and weekly quota meters with
  reset countdowns and absolute rollover times, pace projection with a
  predictive 90 % alert, peak/off-peak badge and share, 24 h / day / week /
  month token charts over a local SQLite history, per-model 24 h usage,
  threshold notifications, bilingual panel and notifications, dual-region
  support, one-time key setup, and tag-gated release automation with
  packaged archives. No code changes from 0.3.0 beyond the version.

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
