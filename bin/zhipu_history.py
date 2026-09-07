"""Persistent consumption history (SQLite) and its aggregations.

Each collector run upserts the last-24h hourly token buckets from the
model-usage endpoint. A bucket's value only grows while its hour is live,
so ``max(existing, incoming)`` per bucket is idempotent, tolerates missed
runs, and needs no diffing of resetting cumulative counters (ADR-0009).
Buckets are local wall time, matching the peak-hour rules.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Final

SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS hourly (
  bucket  TEXT PRIMARY KEY,
  tokens  REAL NOT NULL,
  peak    INTEGER NOT NULL DEFAULT 0,
  updated TEXT NOT NULL
);
"""

RETENTION_DAYS: Final = 400
DAILY_POINTS: Final = 14
WEEKLY_POINTS: Final = 10
MONTHLY_POINTS: Final = 6


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def upsert_hours(conn: sqlite3.Connection, usage: Any) -> None:
    """Merge one run's hourly series; a bucket never shrinks."""
    labels = getattr(usage, "hourLabels", ()) or ()
    tokens = getattr(usage, "tokensByHour", ()) or ()
    peaks = getattr(usage, "peakByHour", ()) or ()
    updated = dt.datetime.now().isoformat(timespec="seconds")
    rows = []
    for index, label in enumerate(labels):
        bucket = f"{str(label).strip()[:13]}:00"
        rows.append((
            bucket,
            float(tokens[index]) if index < len(tokens) else 0.0,
            1 if index < len(peaks) and peaks[index] else 0,
            updated,
        ))
    conn.executemany(
        """
        INSERT INTO hourly (bucket, tokens, peak, updated)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bucket) DO UPDATE SET
          tokens  = MAX(tokens, excluded.tokens),
          peak    = excluded.peak,
          updated = excluded.updated
        """,
        rows,
    )
    conn.commit()


def prune(conn: sqlite3.Connection) -> None:
    cutoff = (dt.datetime.now() - dt.timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    conn.execute("DELETE FROM hourly WHERE bucket < ?", (cutoff,))
    conn.commit()


def _series(conn: sqlite3.Connection, group_expr: str, order_desc: str, limit: int, key_slice: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT {group_expr} AS key, SUM(tokens) AS tokens
        FROM hourly
        GROUP BY key
        ORDER BY {order_desc}
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    points = [{"key": str(key)[:key_slice], "tokens": float(total or 0.0)} for key, total in reversed(rows)]
    return points


def daily_series(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _series(conn, "substr(bucket, 1, 10)", "key DESC", DAILY_POINTS, 10)


def weekly_series(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _series(conn, "strftime('%Y-W%W', bucket)", "key DESC", WEEKLY_POINTS, 8)


def monthly_series(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _series(conn, "substr(bucket, 1, 7)", "key DESC", MONTHLY_POINTS, 7)


def collect_history(db_path: Path, usage: Any) -> dict[str, list[dict[str, Any]]]:
    """Upsert this run's buckets and read the three chart series back."""
    conn = connect(db_path)
    try:
        upsert_hours(conn, usage)
        prune(conn)
        return {
            "daily": daily_series(conn),
            "weekly": weekly_series(conn),
            "monthly": monthly_series(conn),
        }
    finally:
        conn.close()
