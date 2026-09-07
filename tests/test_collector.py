"""Collector behavior tests: quota protocols, credentials, records, notify.

Fixtures come from live captures (2026-09-08, region cn, pro new protocol)
and from payload shapes published in third-party parsers (opencodex quota
provider evidence for the max v2 protocol and legacy flat fields).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(REPO / "bin"))
zf = load_module("zhipu_fetch", REPO / "bin" / "zhipu_fetch.py")
zc = load_module("zhipu_collector", REPO / "bin" / "zhipu_collector.py")
entry = load_module("zhipu_entry", REPO / "bin" / "zhipu-coding-usage")


QUOTA_PRO_NEW = {
    "code": 200, "msg": "操作成功", "success": True,
    "data": {
        "limits": [
            {"type": "CREDIT_LIMIT", "unit": 3, "number": 5, "usage": 12000, "currentValue": 183, "remaining": 11816, "percentage": 1, "nextResetTime": 1788815792820},
            {"type": "CREDIT_LIMIT", "unit": 6, "number": 1, "usage": 60000, "currentValue": 5253, "remaining": 54746, "percentage": 8, "nextResetTime": 1789287746998},
        ],
        "level": "pro",
    },
}

QUOTA_MAX_V2 = {
    "code": 200, "success": True,
    "data": {
        "limits": [
            {"type": "TIME_LIMIT", "usage": 1000, "currentValue": 420, "remaining": 580, "percentage": 42, "nextResetTime": 1790323200000,
             "usageDetails": [{"name": "search-prime", "usage": 220}, {"name": "web-reader", "usage": 88}, {"name": "zread", "usage": 112}]},
            {"type": "TOKENS_LIMIT", "percentage": 63, "remaining": 37, "nextResetTime": 1788815792820},
            {"type": "TOKENS_LIMIT", "percentage": 34, "remaining": 66, "nextResetTime": 1789287746998},
        ],
        "level": "max",
    },
}

QUOTA_OLD_PLAN = {
    "code": 200, "success": True,
    "data": {"limits": [{"type": "TOKENS_LIMIT", "percentage": 55, "remaining": 45, "nextResetTime": 1788815792820}], "level": "lite"},
}

QUOTA_LEGACY = {"data": {"fiveHourPercent": 42, "weeklyPercent": 10, "monthlyMcpUsage": 7, "level": "standard"}}

MODEL_USAGE = {
    "code": 200, "success": True,
    "data": {
        "x_time": ["2026-09-07 19:00", "2026-09-07 20:00"],
        "modelCallCount": [155, 113],
        "tokensUsage": [21616864, 19550094],
        "totalUsage": {
            "totalModelCallCount": 329,
            "totalTokensUsage": 48654815,
            "modelSummaryList": [
                {"modelName": "GLM-5.3", "totalTokens": 48652449, "sortOrder": 1},
                {"modelName": "GLM-5.3-Flash", "totalTokens": 2366, "sortOrder": 2},
            ],
        },
        "modelDataList": [{"modelName": "GLM-5.3", "sortOrder": 1, "tokensUsage": [21000000, 27652449]}],
    },
}

TOOL_USAGE = {
    "code": 200, "success": True,
    "data": {
        "x_time": ["2026-09-07 19:00"],
        "networkSearchCount": [0],
        "webReadMcpCount": [3],
        "zreadMcpCount": [0],
        "totalUsage": {
            "totalNetworkSearchCount": 0,
            "totalWebReadMcpCount": 3,
            "totalZreadMcpCount": 0,
            "totalSearchMcpCount": 3,
            "toolDetails": [{"modelName": "web-reader", "totalUsageCount": 3}],
        },
    },
}


# ---------------------------------------------------------------- protocols


def Test_fiveHourAndWeekly_when_newProtocolHasDiscriminators() -> None:
    level, five_hour, weekly, mcp = zc.parse_quota(QUOTA_PRO_NEW)
    assert level == "pro"
    assert five_hour.present and five_hour.budget == 12000 and five_hour.used == 183
    assert five_hour.percent == 1.5  # recomputed precisely, not the floored API int
    assert weekly.present and weekly.percent == 8.8
    assert not mcp.present


def Test_mcpTools_when_v2ProtocolCarriesTimeLimit() -> None:
    level, five_hour, weekly, mcp = zc.parse_quota(QUOTA_MAX_V2)
    assert level == "max"
    assert five_hour.percent == 63 and weekly.percent == 34  # nextResetTime sort fallback
    assert mcp.present and mcp.percent == 42
    assert [(t.name, t.used) for t in mcp.tools] == [("search-prime", 220.0), ("web-reader", 88.0), ("zread", 112.0)]


def Test_weeklyAbsent_when_oldPlanHasSingleTokensLimit() -> None:
    level, five_hour, weekly, mcp = zc.parse_quota(QUOTA_OLD_PLAN)
    assert level == "lite"
    assert five_hour.present and five_hour.percent == 55
    assert not weekly.present and not mcp.present


def Test_legacyFields_when_limitsEntirelyAbsent() -> None:
    level, five_hour, weekly, mcp = zc.parse_quota(QUOTA_LEGACY)
    assert level == "standard"
    assert five_hour.present and five_hour.percent == 42
    assert weekly.present and weekly.percent == 10
    assert mcp.present and mcp.used == 7


def Test_noLimitsError_when_limitsPresentButEmpty() -> None:
    with pytest.raises(zc.FetchError, match="no-limits"):
        zc.parse_quota({"data": {"limits": [], "level": "pro", "fiveHourPercent": 42}})


def Test_resetMsNormalization_when_stampIsSeconds() -> None:
    assert zc.normalize_reset_ms(1788815792) == 1788815792000
    assert zc.normalize_reset_ms(1788815792820) == 1788815792820
    assert zc.normalize_reset_ms("not-a-number") is None


# ------------------------------------------------------------ usage window


def Test_modelRows_when_modelUsageHasTotalUsage() -> None:
    calls, tokens, models = zc.parse_model_usage(MODEL_USAGE)
    assert calls == 329 and tokens == 48654815.0
    assert [(m.name, m.tokens) for m in models] == [("GLM-5.3", 48652449.0), ("GLM-5.3-Flash", 2366.0)]


def Test_tools24h_when_toolUsageHasTotals() -> None:
    tools = zc.parse_tool_usage(TOOL_USAGE)
    assert (tools.search, tools.web_read, tools.zread) == (0.0, 3.0, 0.0)


def Test_emptyUsage_when_modelUsagePayloadMalformed() -> None:
    assert zc.parse_model_usage({"data": {"totalUsage": None}}) == (0, 0.0, ())
    assert zc.parse_tool_usage({}) == zc.Tools24h(0, 0, 0)


# ------------------------------------------------------------- credentials


def Test_envWinsOverConfigAndAuth_when_zhipuaiEnvSet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth_dir = tmp_path / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(json.dumps({"zhipuai-coding-plan": {"key": "authkey"}}))
    creds = zf.resolve_credentials({"apiKey": "configkey", "region": "cn"}, {"ZHIPUAI_API_KEY": "envkey"})
    assert creds is not None and creds.key == "envkey" and creds.region == "cn" and creds.source == "env:ZHIPUAI_API_KEY"


def Test_regionIntl_when_only_zaiEnvKeySet() -> None:
    creds = zf.resolve_credentials({}, {"ZAI_API_KEY": "intlkey"})
    assert creds is not None and creds.region == "intl"


def Test_opencodeAuthFallback_when_envAndConfigMissing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth_dir = tmp_path / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(json.dumps({"zai-coding-plan": "rawstring"}))
    creds = zf.resolve_credentials({}, {})
    assert creds is not None and creds.key == "rawstring" and creds.region == "intl" and creds.source == "opencode:zai-coding-plan"


def Test_none_when_noKeyAnywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert zf.resolve_credentials({}, {}) is None


# ------------------------------------------------------------------ record


def Test_staleRecordKeepsWindows_when_fetchFailsAfterSuccess() -> None:
    _, five_hour, weekly, mcp = zc.parse_quota(QUOTA_PRO_NEW)
    good = zc.build_record("cn", "pro", five_hour, weekly, mcp, zc.blank_usage(), "2026-09-08T00:00:00Z").to_dict()
    stale = zc.stale_record(good, "unreachable", "cn")
    assert stale["error"] == "unreachable"
    assert stale["fiveHour"]["percent"] == 1.5
    assert stale["fetchedAt"] == "2026-09-08T00:00:00Z"


def Test_blankRecord_when_firstRunFails() -> None:
    stale = zc.stale_record(None, "no-key", "")
    assert stale["error"] == "no-key" and stale["fiveHour"]["present"] is False


def Test_planLabels_when_levelKnownAndUnknown() -> None:
    _, five_hour, weekly, mcp = zc.parse_quota(QUOTA_PRO_NEW)
    record = zc.build_record("cn", "pro", five_hour, weekly, mcp, zc.blank_usage(), "")
    assert record.planLabel == "Pro"
    exotic = zc.build_record("cn", "ultra", five_hour, weekly, mcp, zc.blank_usage(), "")
    assert exotic.planLabel == "Ultra"


# -------------------------------------------------------------- notifications


def Test_notifyFiresHighestNewThreshold_when_crossed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fired_calls: list[str] = []

    def fake_fire(summary: str, body: str, critical: bool) -> bool:
        fired_calls.append(summary)
        return True

    monkeypatch.setattr(entry, "_fire_notification", fake_fire)
    monkeypatch.setattr(entry, "state_paths", lambda: (tmp_path / "usage.json", tmp_path / "notify-state.json", tmp_path / "config.json"))

    _, five_hour, weekly, mcp = zc.parse_quota(QUOTA_MAX_V2)
    record = zc.build_record("cn", "max", five_hour, weekly, mcp, zc.blank_usage(), "").to_dict()
    entry.maybe_notify(record, enabled=True)

    assert fired_calls == []  # 63% crosses nothing on any window
    record["weekly"]["percent"] = 91.0
    entry.maybe_notify(record, enabled=True)
    assert len(fired_calls) == 1 and "weekly quota at 91%" in fired_calls[0]

    state = json.loads((tmp_path / "notify-state.json").read_text())
    assert any(key.startswith("weekly@") for key in state["fired"])

    entry.maybe_notify(record, enabled=True)  # same cycle identity: deduped
    assert len(fired_calls) == 1


def Test_notifyBody_when_budgetKnown() -> None:
    body = entry._notify_body("weekly", 90, {"used": 54000, "budget": 60000})
    assert "90%" in body and "54,000 of 60,000" in body
    assert "exhausted" in entry._notify_body("weekly", 100, {"used": 1, "budget": 2})
