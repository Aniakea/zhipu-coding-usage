"""Pace and peak-hour derivations for the usage record.

Pure functions over primitives: no I/O, no clocks beyond the ``now``/labels
handed in, no imports from the other plugin modules. Rules come from the
published plan docs — peak window Mon–Fri 14:00–18:00 local time at a 3×
coefficient, 1× elsewhere (``docs/adr/0008`` records the local-time
assumption).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

PEAK_START_HOUR: Final = 14
PEAK_END_HOUR: Final = 18  # exclusive
WEEK_MS: Final = 7 * 86400_000
PROJECTION_MIN_ELAPSED_MS: Final = 2 * 3600_000
PREDICT_THRESHOLD: Final = 0.90


@dataclass(frozen=True, slots=True)
class PeakInfo:
    peakNow: bool
    offPeakShare24h: float | None


@dataclass(frozen=True, slots=True)
class Projection:
    exhaustsAtMs: int
    hoursRemaining: float
    hoursToThreshold: float | None


def is_peak(moment: dt.datetime) -> bool:
    return moment.weekday() < 5 and PEAK_START_HOUR <= moment.hour < PEAK_END_HOUR


def bucket_is_peak(label: str) -> bool:
    """Peak classification for one ``YYYY-MM-DD HH:MM`` series label."""
    try:
        moment = dt.datetime.strptime(label.strip()[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    return is_peak(moment)


def peak_info(now: dt.datetime, hour_labels: tuple[str, ...], tokens_by_hour: tuple[float, ...]) -> PeakInfo:
    """Share of the 24 h token consumption that fell outside the peak window."""
    off_peak = total = 0.0
    for label, tokens in zip(hour_labels, tokens_by_hour):
        total += tokens
        if not bucket_is_peak(label):
            off_peak += tokens
    return PeakInfo(is_peak(now), round(off_peak / total, 4) if total > 0 else None)


def weekly_projection(now_ms: int, used: float, budget: float, resets_at_ms: int) -> Projection | None:
    """Where the weekly budget lands if the rest of the cycle burns like the
    part already spent. Stays unset before two hours of cycle have elapsed
    (a sliver extrapolates absurdly), when the pace outlasts the reset, and
    when the quota is already gone."""
    start_ms = resets_at_ms - WEEK_MS
    elapsed_ms = now_ms - start_ms
    if elapsed_ms < PROJECTION_MIN_ELAPSED_MS:
        return None
    if budget <= 0 or used <= 0:
        return None
    rate = used / elapsed_ms
    remaining = budget - used
    if remaining <= 0:
        return None
    ms_remaining = remaining / rate
    exhausts_at = int(now_ms + ms_remaining)
    if exhausts_at >= resets_at_ms:
        return None  # pace outlasts the cycle — nothing to warn about
    threshold_credits = budget * PREDICT_THRESHOLD - used
    hours_to_threshold = threshold_credits / rate / 3600_000 if threshold_credits > 0 else None
    return Projection(exhaustsAtMs=exhausts_at, hoursRemaining=ms_remaining / 3600_000, hoursToThreshold=hours_to_threshold)
