# ADR 0009 — Consumption history (SQLite) and line charts

- **Status**: Accepted (2026-09-08)

## Context

Day/week/month consumption trends need history the API does not keep: the
monitor endpoints only expose the last 24 h per hour. Two accumulation
strategies were considered:

1. **Diff cumulative counters** between runs (e.g. weekly `currentValue`) —
   fragile: every window reset drops the counter to 0, so every diff needs
   reset-aware patching, and missed runs silently lose consumption.
2. **Upsert hourly buckets** from the `model-usage` series — a bucket's
   value only grows while its hour is live and is final afterwards, so
   `MAX(existing, incoming)` per bucket is idempotent, tolerates missed
   runs with at most one under-filled live hour, and needs no diffing.

## Decision

**Strategy 2.** `bin/zhipu_history.py` owns a SQLite database at
`~/.local/state/omarchy/zhipu/history.db`:

- one table `hourly(bucket TEXT PRIMARY KEY, tokens REAL, peak INTEGER,
  updated TEXT)` with buckets in local wall time (`YYYY-MM-DD HH:00`),
  upserted on every successful collection;
- day / week / month series are `GROUP BY` views (14 days, 10 ISO weeks,
  6 months), read back into the record's `history` field;
- retention pruned to 400 days.

The panel draws all consumption charts as **polyline charts** (Canvas):
one shared `LineChart` component (line + soft area fill + sparse x labels +
per-point hover tooltips), fed by a range switcher — **24h** (live buckets,
peak-hour points marked), **day / week / month** (SQLite aggregates).

## Consequences

- No extra API calls; the collector's existing model-usage fetch is the
  only input.
- First run shows a single day point; the series grow as the plugin runs.
  History cannot be backfilled — the API does not expose it.
- The DB is disposable state: deleting it only costs chart history, never
  the live windows (documented in the README's removal section).
- Buckets are wall-clock local; DST shifts mis-file at most one bucket.
