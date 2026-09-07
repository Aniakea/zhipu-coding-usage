# ADR 0008 — Insights (peak hours, pace projection) and i18n

- **Status**: Accepted (2026-09-08)

## Context

The quota payloads already describe *state* (how full each window is) but not
*trajectory* (where the week is heading) or *cost structure* (when tokens are
being burned). The plan docs publish a peak window — Mon–Fri 14:00–18:00 at a
3× coefficient, 1× elsewhere — and the weekly window carries enough to
extrapolate a burn rate. Meanwhile the panel is English-only while most of
the audience is Chinese.

## Decision

- **`bin/zhipu_insights.py`** — pure functions over primitives, importing
  nothing from the other plugin modules (keeps the import graph acyclic):
  - `peak_info()` — whether *now* is peak, and the share of the 24 h token
    consumption that fell off-peak (per-bucket classification from the
    hourly labels).
  - `weekly_projection()` — burn-rate extrapolation from
    `used / elapsed`, returning the projected exhaustion instant, hours
    remaining, and hours to the 90 % mark. Unset before 2 h of cycle have
    elapsed, when the pace outlasts the reset, or when the quota is gone.
- **Peak rules are local wall time**, matching how the plan's audience
  experiences them; documented as an assumption, cheap to change via the
  two constants. Naive-datetime lints are scoped off in `pyproject.toml`
  for exactly these modules.
- **Predictive notification** — once per weekly cycle, when the projection
  says the 90 % mark is ≤ 6 h away: "on the current pace it reaches 90 % in
  ~5 h" (dedup key `weekly-predict90@<reset>`).
- **i18n** — `language` widget setting (`auto`/`en`/`zh`; auto follows
  `Qt.locale()`), a string table + per-language formatters in `Model.js`
  (countdown word order differs: "resets in 3h" vs "3 小时后重置"), and
  notification strings in the entry driven by a config `language` value
  (`auto` → `LANG` prefix). Brand name and model names stay untranslated.

## Consequences

- The projection is a linear read of a noisy rate; the 2 h floor and the
  outlasts-reset cutoff keep it from narrating nonsense early or late in
  the cycle.
- Peak hours may be adjusted by the provider ("dynamic parameters"); the
  constants are the single point to update.
- Adding a language = one table entry in `Model.js` plus notification
  templates in the entry.
