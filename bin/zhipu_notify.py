"""Desktop notifications and the atomic JSON writer they persist through.

Threshold crossing (per window/cycle), the predictive 90 % approach alert,
once-per-cycle dedup state, and bilingual notification text. Pure policy +
I/O helpers; quota parsing and collection live elsewhere.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path
from typing import Any, Final

from zhipu_secure import notify_send_executable, read_json_bounded, write_json_atomic

NOTIFY_RULES: Final[dict[str, tuple[int, ...]]] = {
    "fiveHour": (90,),
    "weekly": (75, 90, 100),
}
NOTIFY_WINDOW_LABELS: Final[dict[str, dict[str, str]]] = {
    "fiveHour": {"en": "5-hour window", "zh": "5 小时额度"},
    "weekly": {"en": "weekly quota", "zh": "每周额度"},
}
NOTIFY_STATE_MAX_AGE_DAYS: Final = 60
PREDICT_HOURS_AHEAD: Final = 6.0
PREDICT_THRESHOLD_PCT: Final = 90

NOTIFY_TEXT: Final[dict[str, dict[str, str]]] = {
    "en": {
        "predict_title": "Zhipu weekly quota heading for {pct}%",
        "predict_body": "On the current pace it reaches {pct}% in about {hours}. Slowing down now keeps the week covered.",
        "threshold_body": "{label} has reached {pct}%.{counts}",
        "exhausted_body": "{label} is exhausted.{counts}",
        "summary": "Zhipu {label} at {pct}%",
    },
    "zh": {
        "predict_title": "智谱周额度即将到达 {pct}%",
        "predict_body": "按当前速率约 {hours}后触及 {pct}%。现在放缓可保本周额度够用。",
        "threshold_body": "{label}已到达 {pct}%。{counts}",
        "exhausted_body": "{label}已耗尽。{counts}",
        "summary": "智谱{label}已用 {pct}%",
    },
}


def notify_lang(config: dict[str, Any]) -> str:
    configured = str(config.get("language") or "").strip().lower()
    if configured in ("en", "zh"):
        return configured
    if configured == "auto" or configured == "":
        return "zh" if os.environ.get("LANG", "").lower().startswith("zh") else "en"
    return "en"


def _hours_text(hours: float, lang: str) -> str:
    if hours >= 24:
        return f"{hours / 24:.0f}d" if lang == "en" else f"{hours / 24:.0f} 天"
    return f"{hours:.0f}h" if lang == "en" else f"{hours:.0f} 小时"


def _notify_body(window_name: str, threshold: int, window: dict[str, Any], lang: str) -> str:
    label = NOTIFY_WINDOW_LABELS[window_name][lang]
    used = window.get("used")
    budget = window.get("budget")
    counts = ""
    if isinstance(used, (int, float)) and isinstance(budget, (int, float)) and budget > 0:
        counts = f" — {used:,.0f} of {budget:,.0f} used"
        if lang == "zh":
            counts = f"——已用 {used:,.0f} / {budget:,.0f}"
    template = NOTIFY_TEXT[lang]["exhausted_body"] if threshold >= 100 else NOTIFY_TEXT[lang]["threshold_body"]
    return template.format(label=label, pct=threshold, counts=counts)


def _fire_notification(summary: str, body: str, critical: bool) -> bool:
    executable = notify_send_executable()
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [
                executable,
                "--app-name=Zhipu Coding Usage",
                f"--urgency={'critical' if critical else 'normal'}",
                "--icon=dialog-information",
                summary,
                body,
            ],
            check=False,
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def maybe_notify(record: dict[str, Any], enabled: bool, lang: str, notify_state_path: Path) -> None:
    if not enabled or record.get("error") != "":
        return
    fired = read_json_bounded(notify_state_path).get("fired", {})
    if not isinstance(fired, dict):
        fired = {}

    now = dt.datetime.now(dt.timezone.utc)
    fresh: dict[str, str] = {}
    texts = NOTIFY_TEXT[lang]
    for window_name, thresholds in NOTIFY_RULES.items():
        window = record.get(window_name)
        if not isinstance(window, dict) or window.get("present") is not True:
            continue
        percent = window.get("percent")
        if not isinstance(percent, (int, float)):
            continue
        crossed = max((t for t in thresholds if percent >= t), default=None)
        if crossed is None:
            continue
        identity = f"{window_name}@{window.get('resetsAtMs') or 'static'}"
        if identity in fired:
            continue
        summary = texts["summary"].format(
            label=NOTIFY_WINDOW_LABELS[window_name][lang],
            pct=f"{percent:.0f}",
        )
        if _fire_notification(summary, _notify_body(window_name, crossed, window, lang), crossed >= 100):
            fresh[identity] = now.isoformat()

    projection = record.get("projection")
    weekly = record.get("weekly")
    if (
        isinstance(projection, dict)
        and isinstance(weekly, dict)
        and isinstance(projection.get("hoursToThreshold"), (int, float))
        and not weekly.get("percent", 0) >= PREDICT_THRESHOLD_PCT
    ):
        hours = float(projection["hoursToThreshold"])
        identity = f"weekly-predict{PREDICT_THRESHOLD_PCT}@{weekly.get('resetsAtMs') or 'static'}"
        if 0 < hours <= PREDICT_HOURS_AHEAD and identity not in fired:
            title = texts["predict_title"].format(pct=PREDICT_THRESHOLD_PCT)
            body = texts["predict_body"].format(hours=_hours_text(hours, lang), pct=PREDICT_THRESHOLD_PCT)
            if _fire_notification(title, body, critical=False):
                fresh[identity] = now.isoformat()

    if not fresh:
        return
    fired.update(fresh)
    cutoff = (now - dt.timedelta(days=NOTIFY_STATE_MAX_AGE_DAYS)).isoformat()
    pruned = {key: at for key, at in fired.items() if at >= cutoff}
    try:
        write_json_atomic(notify_state_path, {"fired": pruned})
    except OSError:
        return  # A repeated notification beats a failed run.
