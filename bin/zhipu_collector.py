"""Zhipu Coding Plan usage collector — parse and record layer.

Pure data work: typed window/model objects from the monitor payloads (ADR-0003
rules), record shaping, and the stale-merge that keeps the last good numbers
on screen through a network failure. No I/O — fetching lives in
``zhipu_fetch``, file writes and notifications in the ``zhipu-coding-usage``
entry point.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from typing import Any, Final

from zhipu_fetch import FetchError

LEVEL_LABELS: Final[dict[str, str]] = {
    "lite": "Lite",
    "standard": "Standard",
    "pro": "Pro",
    "max": "Max",
}


@dataclass(frozen=True, slots=True)
class Window:
    """One quota window, display-ready. ``present`` False renders as "—"."""

    present: bool
    percent: float | None
    used: float | None
    budget: float | None
    remaining: float | None
    resetsAtMs: int | None

    def resets_at_iso(self) -> str:
        if self.resetsAtMs is None:
            return ""
        stamp = dt.datetime.fromtimestamp(self.resetsAtMs / 1000, dt.timezone.utc)
        return stamp.isoformat().replace("+00:00", "Z")


ABSENT_WINDOW: Final = Window(False, None, None, None, None, None)


@dataclass(frozen=True, slots=True)
class ToolUse:
    name: str
    used: float


@dataclass(frozen=True, slots=True)
class MonthlyMcp(Window):
    tools: tuple[ToolUse, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelRow:
    name: str
    tokens: float


@dataclass(frozen=True, slots=True)
class Tools24h:
    search: float
    web_read: float
    zread: float


@dataclass(frozen=True, slots=True)
class Usage24h:
    calls: int
    tokens: float
    models: tuple[ModelRow, ...]
    tools: Tools24h


@dataclass(frozen=True, slots=True)
class Record:
    schema: int
    agent: str
    agentName: str
    generatedAt: str
    fetchedAt: str
    error: str
    region: str
    planLevel: str
    planLabel: str
    fiveHour: Window
    weekly: Window
    monthlyMcp: MonthlyMcp
    usage24h: Usage24h

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["fiveHour"]["resetsAt"] = self.fiveHour.resets_at_iso()
        out["weekly"]["resetsAt"] = self.weekly.resets_at_iso()
        out["monthlyMcp"]["resetsAt"] = self.monthlyMcp.resets_at_iso()
        return out


# --------------------------------------------------------------------- clock


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_reset_ms(raw: Any) -> int | None:
    """Zhipu stamps are epoch ms; tolerate seconds and strings."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return int(value if value > 1e12 else value * 1000)


def _number(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value


# ------------------------------------------------------------------- parse


def _window_from_row(row: dict[str, Any]) -> Window:
    used = _number(row.get("currentValue"))
    budget = _number(row.get("usage"))
    if used is not None and budget:
        # API percentage floors to int (1.525 -> 1); recompute for the meter.
        percent: float | None = used / budget * 100.0
    else:
        percent = _number(row.get("percentage"))
    return Window(
        present=True,
        percent=None if percent is None else round(percent, 1),
        used=used,
        budget=budget,
        remaining=_number(row.get("remaining")),
        resetsAtMs=normalize_reset_ms(row.get("nextResetTime")),
    )


def _tools_from_details(raw: Any) -> tuple[ToolUse, ...]:
    if not isinstance(raw, list):
        return ()
    tools: list[ToolUse] = []
    for detail in raw:
        if not isinstance(detail, dict):
            continue
        name = str(detail.get("modelName") or detail.get("name") or detail.get("toolName") or "").strip()
        used = _number(detail.get("totalUsageCount")) or _number(detail.get("usage")) or 0.0
        if name:
            tools.append(ToolUse(name, used))
    return tuple(tools)


def _classify_token_rows(rows: list[dict[str, Any]]) -> tuple[Window, Window]:
    five_hour = ABSENT_WINDOW
    weekly = ABSENT_WINDOW
    leftovers: list[Window] = []
    for row in rows:
        window = _window_from_row(row)
        # Literals, not constants: a bare name in a case pattern captures.
        match row.get("unit"), row.get("number"):
            case 3, 5:
                five_hour = window
            case 6, 1:
                weekly = window
            case _:
                leftovers.append(window)
    if not five_hour.present or not weekly.present:
        by_reset = sorted(leftovers, key=lambda w: w.resetsAtMs or 0)
        if not five_hour.present and by_reset:
            five_hour = by_reset.pop(0)
        if not weekly.present and by_reset:
            weekly = by_reset.pop(0)
    return five_hour, weekly


def parse_quota(payload: Any) -> tuple[str, Window, Window, MonthlyMcp]:
    """ADR-0003 rules: structured ``limits`` first, legacy flat fields only
    when ``limits`` is entirely absent."""
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        raise FetchError("bad-payload")

    level = str(data.get("level") or "").strip().lower()
    limits = data.get("limits")

    if isinstance(limits, list):
        token_rows: list[dict[str, Any]] = []
        mcp = MonthlyMcp(False, None, None, None, None, None, ())
        for row in limits:
            if not isinstance(row, dict):
                continue
            match row.get("type"):
                case "TOKENS_LIMIT" | "CREDIT_LIMIT":
                    token_rows.append(row)
                case "TIME_LIMIT":
                    mcp = MonthlyMcp(**asdict(_window_from_row(row)), tools=_tools_from_details(row.get("usageDetails")))
                case _:
                    continue
        if not token_rows and not mcp.present:
            raise FetchError("no-limits")
        five_hour, weekly = _classify_token_rows(token_rows)
        return level, five_hour, weekly, mcp

    if "limits" in data:
        # Present-but-empty (or non-list) must not fall through to legacy.
        raise FetchError("no-limits")

    legacy_five = _number(data.get("fiveHourPercent"))
    legacy_weekly = _number(data.get("weeklyPercent"))
    mcp_used = _number(data.get("monthlyMcpUsage"))
    five_hour = Window(True, legacy_five, None, None, None, None) if legacy_five is not None else ABSENT_WINDOW
    weekly = Window(True, legacy_weekly, None, None, None, None) if legacy_weekly is not None else ABSENT_WINDOW
    monthly = MonthlyMcp(
        True,
        None if mcp_used is None else round(mcp_used, 1),
        mcp_used,
        None,
        None,
        None,
        (),
    ) if mcp_used is not None else MonthlyMcp(False, None, None, None, None, None, ())
    return level, five_hour, weekly, monthly


def parse_model_usage(payload: Any) -> tuple[int, float, tuple[ModelRow, ...]]:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    total = data.get("totalUsage") if isinstance(data, dict) else None
    if not isinstance(total, dict):
        return 0, 0.0, ()
    calls = int(_number(total.get("totalModelCallCount")) or 0)
    tokens = _number(total.get("totalTokensUsage")) or 0.0
    models: list[ModelRow] = []
    for row in total.get("modelSummaryList") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("modelName") or "").strip()
        row_tokens = _number(row.get("totalTokens")) or 0.0
        if name and row_tokens > 0:
            models.append(ModelRow(name, row_tokens))
    models.sort(key=lambda m: m.tokens, reverse=True)
    return calls, tokens, tuple(models[:10])


def parse_tool_usage(payload: Any) -> Tools24h:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    total = data.get("totalUsage") if isinstance(data, dict) else None
    if not isinstance(total, dict):
        return Tools24h(0, 0, 0)
    return Tools24h(
        search=_number(total.get("totalNetworkSearchCount")) or 0.0,
        web_read=_number(total.get("totalWebReadMcpCount")) or 0.0,
        zread=_number(total.get("totalZreadMcpCount")) or 0.0,
    )


# ------------------------------------------------------------------ record


def blank_usage() -> Usage24h:
    return Usage24h(0, 0.0, (), Tools24h(0, 0, 0))


def build_record(
    region: str,
    level: str,
    five_hour: Window,
    weekly: Window,
    mcp: MonthlyMcp,
    usage: Usage24h,
    fetched_at: str,
) -> Record:
    label = LEVEL_LABELS.get(level, level[:1].upper() + level[1:] if level else "")
    return Record(
        schema=1,
        agent="zhipu",
        agentName="Zhipu Coding Plan",
        generatedAt=utcnow_iso(),
        fetchedAt=fetched_at,
        error="",
        region=region,
        planLevel=level,
        planLabel=label or "Coding Plan",
        fiveHour=five_hour,
        weekly=weekly,
        monthlyMcp=mcp,
        usage24h=usage,
    )


def stale_record(previous: dict[str, Any] | None, error: str, region: str) -> dict[str, Any]:
    """Failure path: keep the last good windows, stamp the error, stay honest."""
    if isinstance(previous, dict) and previous.get("error") == "":
        record = dict(previous)
        record["generatedAt"] = utcnow_iso()
        record["error"] = error
        record["region"] = region or str(record.get("region") or "")
        return record
    blank = build_record(region, "", ABSENT_WINDOW, ABSENT_WINDOW, MonthlyMcp(False, None, None, None, None, None, ()), blank_usage(), "")
    out = blank.to_dict()
    out["generatedAt"] = utcnow_iso()
    out["error"] = error
    return out
