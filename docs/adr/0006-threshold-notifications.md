# ADR 0006 — Threshold desktop notifications

- **Status**: Accepted (2026-09-08)

## Context

copilot-companion notifies at 75 / 90 / 100 % once per monthly cycle. Our
three windows reset at very different cadences: the 5-hour rolling window
resets constantly, so per-level notifications would fire many times a day.

## Decision (user decision, Round 2)

| Window | Thresholds | Once-per |
| --- | --- | --- |
| 5-hour | **90 % only** | window (identified by its `nextResetTime`) |
| Weekly | 75 / 90 / 100 % | week (identified by `nextResetTime`) |
| MCP monthly | 75 / 90 / 100 % | month (identified by `nextResetTime`) |

Mechanics:

- Delivery via `notify-send` (libnotify) if present; absent ⇒ silently skip
  (panel unaffected).
- Dedup state persisted in `~/.local/state/omarchy/zhipu/notify-state.json`,
  keyed by `windowType + threshold + nextResetTime`; crossing detection uses
  the fetched percentage, pruned of stale keys on write.
- `"notify": false` in the config file disables entirely.
- Fired by the **collector** (not QML), so notifications work even while the
  panel is closed.

## Consequences

- At most 7 notifications per week per account in the worst case.
- Reset-time-as-cycle-id survives collector restarts and clock skew better
  than wall-clock bucketing.
- 100 % notification doubles as "quota exhausted right now" signal for the
  weekly window.

## Amendment (2026-09-08)

The `monthlyMcp` rule row is removed with the MCP monthly feature; monitored
windows are the 5-hour (90 %) and weekly (75/90/100 %) only.

## Second amendment (2026-09-11, per-threshold identity)

The dedup identity now carries the crossed threshold exactly as the
mechanics above specify (`window@threshold@nextResetTime`). Before v1.0.3
the identity omitted the threshold, so within one weekly cycle the 75 %
notification permanently silenced the 90 % and 100 % alerts; a regression
test locks the 75→90→100 progression.
