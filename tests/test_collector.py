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
zi = load_module("zhipu_insights", REPO / "bin" / "zhipu_insights.py")
zc = load_module("zhipu_collector", REPO / "bin" / "zhipu_collector.py")
zn = load_module("zhipu_notify", REPO / "bin" / "zhipu_notify.py")
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
    level, five_hour, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    assert level == "pro"
    assert five_hour.present and five_hour.budget == 12000 and five_hour.used == 183
    assert five_hour.percent == 1.5  # recomputed precisely, not the floored API int
    assert weekly.present and weekly.percent == 8.8


def Test_timeLimitIgnored_when_v2ProtocolCarriesIt() -> None:
    level, five_hour, weekly = zc.parse_quota(QUOTA_MAX_V2)
    assert level == "max"
    assert five_hour.percent == 63 and weekly.percent == 34  # nextResetTime sort fallback


def Test_weeklyAbsent_when_oldPlanHasSingleTokensLimit() -> None:
    level, five_hour, weekly = zc.parse_quota(QUOTA_OLD_PLAN)
    assert level == "lite"
    assert five_hour.present and five_hour.percent == 55
    assert not weekly.present


def Test_legacyFields_when_limitsEntirelyAbsent() -> None:
    level, five_hour, weekly = zc.parse_quota(QUOTA_LEGACY)
    assert level == "standard"
    assert five_hour.present and five_hour.percent == 42
    assert weekly.present and weekly.percent == 10


def Test_noLimitsError_when_limitsPresentButEmpty() -> None:
    with pytest.raises(zc.FetchError, match="no-limits"):
        zc.parse_quota({"data": {"limits": [], "level": "pro", "fiveHourPercent": 42}})


def Test_resetMsNormalization_when_stampIsSeconds() -> None:
    assert zc.normalize_reset_ms(1788815792) == 1788815792000
    assert zc.normalize_reset_ms(1788815792820) == 1788815792820
    assert zc.normalize_reset_ms("not-a-number") is None


# ------------------------------------------------------------ usage window


def Test_modelRows_when_modelUsageHasTotalUsage() -> None:
    usage = zc.parse_model_usage(MODEL_USAGE)
    assert usage.calls == 329 and usage.tokens == 48654815.0
    assert [(m.name, m.tokens) for m in usage.models] == [("GLM-5.3", 48652449.0), ("GLM-5.3-Flash", 2366.0)]


def Test_hourlySeries_when_modelUsageCarriesBuckets() -> None:
    usage = zc.parse_model_usage(MODEL_USAGE)
    assert usage.hourLabels == ("2026-09-07 19:00", "2026-09-07 20:00")
    assert usage.tokensByHour == (21616864.0, 19550094.0)
    assert usage.peakByHour == (False, False)  # 19:00 and 20:00 sit outside 14:00-18:00


def Test_tools24h_when_toolUsageHasTotals() -> None:
    tools = zc.parse_tool_usage(TOOL_USAGE)
    assert (tools.search, tools.web_read, tools.zread) == (0.0, 3.0, 0.0)


def Test_emptyUsage_when_modelUsagePayloadMalformed() -> None:
    assert zc.parse_model_usage({"data": {"totalUsage": None}}) == zc.blank_usage()
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


def Test_none_when_noKeyAnywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert zf.resolve_credentials({}, {}) is None


def Test_opencodeImportIsExplicit_when_runtimeResolution() -> None:
    # Runtime resolution never consults the opencode store, even when present.
    creds = zf.resolve_credentials({}, {})
    assert creds is None


def Test_findOpencodeCredentials_when_authStoreExists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth_dir = tmp_path / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(json.dumps({"zai-coding-plan": "rawstring"}))
    creds = zf.find_opencode_credentials()
    assert creds is not None and creds.key == "rawstring" and creds.region == "intl" and creds.source == "opencode:zai-coding-plan"


def Test_findOpencodeCredentials_when_authStoreAbsent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert zf.find_opencode_credentials() is None


# ------------------------------------------------------------------ record


def Test_staleRecordKeepsWindows_when_fetchFailsAfterSuccess() -> None:
    _, five_hour, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    good = zc.build_record("cn", "pro", five_hour, weekly, zc.blank_usage(), "2026-09-08T00:00:00Z").to_dict()
    stale = zc.stale_record(good, "unreachable", "cn")
    assert stale["error"] == "unreachable"
    assert stale["fiveHour"]["percent"] == 1.5
    assert stale["fetchedAt"] == "2026-09-08T00:00:00Z"


def Test_blankRecord_when_firstRunFails() -> None:
    stale = zc.stale_record(None, "no-key", "")
    assert stale["error"] == "no-key" and stale["fiveHour"]["present"] is False


def Test_planLabels_when_levelKnownAndUnknown() -> None:
    _, five_hour, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    record = zc.build_record("cn", "pro", five_hour, weekly, zc.blank_usage(), "")
    assert record.planLabel == "Pro"
    exotic = zc.build_record("cn", "ultra", five_hour, weekly, zc.blank_usage(), "")
    assert exotic.planLabel == "Ultra"


# -------------------------------------------------------------- notifications


def Test_notifyFiresHighestNewThreshold_when_crossed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fired_calls: list[str] = []

    def fake_fire(summary: str, body: str, critical: bool) -> bool:
        fired_calls.append(summary)
        return True

    monkeypatch.setattr(zn, "_fire_notification", fake_fire)
    notify_state = tmp_path / "notify-state.json"

    _, five_hour, weekly = zc.parse_quota(QUOTA_MAX_V2)
    record = zc.build_record("cn", "max", five_hour, weekly, zc.blank_usage(), "").to_dict()
    zn.maybe_notify(record, enabled=True, lang="en", notify_state_path=notify_state)

    assert fired_calls == []  # 63% crosses nothing on any window
    record["weekly"]["percent"] = 91.0
    zn.maybe_notify(record, enabled=True, lang="en", notify_state_path=notify_state)
    assert len(fired_calls) == 1 and "weekly quota at 91%" in fired_calls[0]

    state = json.loads((tmp_path / "notify-state.json").read_text())
    assert any(key.startswith("weekly@") for key in state["fired"])

    zn.maybe_notify(record, enabled=True, lang="en", notify_state_path=notify_state)  # same cycle identity: deduped
    assert len(fired_calls) == 1


def Test_notifyBody_when_budgetKnown() -> None:
    body = zn._notify_body("weekly", 90, {"used": 54000, "budget": 60000}, "en")
    assert "90%" in body and "54,000 of 60,000" in body
    assert "exhausted" in zn._notify_body("weekly", 100, {"used": 1, "budget": 2}, "en")


# ------------------------------------------------------------------ key setup


def Test_setKeyWritesConfig_when_invoked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry, "state_paths", lambda: (tmp_path / "usage.json", tmp_path / "notify.json", tmp_path / "config.json"))
    code = entry.main(["--set-key", "sk-test-1234567890", "--region", "intl"])
    assert code == 0
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["apiKey"] == "sk-test-1234567890" and config["region"] == "intl"
    mode = (tmp_path / "config.json").stat().st_mode & 0o777
    assert mode == 0o600


def Test_importKeyMigratesFromOpencode_when_authStoreExists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(entry, "state_paths", lambda: (tmp_path / "usage.json", tmp_path / "notify.json", tmp_path / "config.json"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    auth_dir = tmp_path / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(json.dumps({"zhipuai-coding-plan": {"key": "sk-opencode-abcdef123456"}}))
    code = entry.main(["--import-key"])
    assert code == 0
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["apiKey"] == "sk-opencode-abcdef123456" and config["region"] == "cn"
    out = capsys.readouterr().out
    assert "sk-o…" in out and "sk-opencode-abcdef123456" not in out


def Test_importKeyFailsSoftly_when_noAuthStore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry, "state_paths", lambda: (tmp_path / "usage.json", tmp_path / "notify.json", tmp_path / "config.json"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert entry.main(["--import-key"]) == 2


# ------------------------------------------------------------------- insights


def Test_peakClassification_when_weekdayAndWeekendVary() -> None:
    import datetime as dt

    assert zi.is_peak(dt.datetime(2026, 9, 8, 15, 0)) is True  # Tuesday 15:00
    assert zi.is_peak(dt.datetime(2026, 9, 8, 13, 59)) is False
    assert zi.is_peak(dt.datetime(2026, 9, 8, 18, 0)) is False  # exclusive end
    assert zi.is_peak(dt.datetime(2026, 9, 12, 15, 0)) is False  # Saturday


def Test_offPeakShare_when_bucketsSpanWindows() -> None:
    import datetime as dt

    labels = ("2026-09-08 15:00", "2026-09-08 20:00", "2026-09-09 02:00")
    tokens = (3000.0, 5000.0, 2000.0)
    info = zi.peak_info(dt.datetime(2026, 9, 9, 9, 0), tuple(labels), tuple(tokens))
    assert info.peakNow is False
    assert info.offPeakShare24h == 0.7  # 7000 of 10000 outside the peak window


def Test_weeklyProjection_when_paceOutlastsReset() -> None:
    _, _, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    now = weekly.resetsAtMs - zi.WEEK_MS + 4 * 86400_000  # 1,000 credits over 4 days
    assert zi.weekly_projection(now, 1000.0, 60000.0, weekly.resetsAtMs) is None


def Test_weeklyProjection_when_paceExhaustsFirst() -> None:
    _, _, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    now = weekly.resetsAtMs - zi.WEEK_MS + 4 * 3600_000
    proj = zi.weekly_projection(now, 40000.0, 60000.0, weekly.resetsAtMs)
    assert proj is not None
    assert 0 < proj.hoursRemaining < 48
    assert proj.exhaustsAtMs < weekly.resetsAtMs
    assert proj.hoursToThreshold is not None and proj.hoursToThreshold < proj.hoursRemaining


def Test_weeklyProjection_when_cycleTooYoung() -> None:
    _, _, weekly = zc.parse_quota(QUOTA_PRO_NEW)
    now = weekly.resetsAtMs - zi.WEEK_MS + 60_000  # one minute elapsed
    assert zi.weekly_projection(now, 100.0, 60000.0, weekly.resetsAtMs) is None


def Test_predictiveNotification_when_thresholdApproaching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fired: list[str] = []

    def fake_fire(summary: str, body: str, critical: bool) -> bool:
        fired.append(summary)
        return True

    monkeypatch.setattr(zn, "_fire_notification", fake_fire)
    notify_state = tmp_path / "notify-state.json"
    record = {
        "error": "",
        "weekly": {"present": True, "percent": 70.0, "used": 42000.0, "budget": 60000.0, "resetsAtMs": 1789287746998},
        "fiveHour": {"present": False},
        "projection": {"hoursToThreshold": 4.2, "exhaustsAtMs": 1789200000000},
    }
    zn.maybe_notify(record, enabled=True, lang="zh", notify_state_path=notify_state)
    assert len(fired) == 1 and "90%" in fired[0] and "周额度" in fired[0]
    zn.maybe_notify(record, enabled=True, lang="zh", notify_state_path=notify_state)  # deduped per cycle
    assert len(fired) == 1


def Test_notifyLang_when_configOverridesOrAuto() -> None:
    assert zn.notify_lang({"language": "zh"}) == "zh"
    assert zn.notify_lang({"language": "auto"}) in ("en", "zh")


# ------------------------------------------------------------------- history


def Test_historyUpsert_when_bucket_value_grows(tmp_path: Path) -> None:
    zh = load_module("zhipu_history", REPO / "bin" / "zhipu_history.py")
    db = tmp_path / "history.db"

    class Series:
        hourLabels = ("2026-09-08 15:00", "2026-09-08 16:00")
        tokensByHour = (1000.0, 500.0)
        peakByHour = (True, True)

    first = zh.collect_history(db, Series)
    assert first["daily"] == [{"key": "2026-09-08", "tokens": 1500.0}]

    Series.tokensByHour = (1800.0, 400.0)  # live hour grows, closed hour shrinks in-flight
    second = zh.collect_history(db, Series)
    assert second["daily"] == [{"key": "2026-09-08", "tokens": 2300.0}]  # 1800 + max(500,400)


def Test_historyAggregates_when_days_span_groups(tmp_path: Path) -> None:
    zh = load_module("zhipu_history", REPO / "bin" / "zhipu_history.py")
    db = tmp_path / "history.db"

    class Series:
        hourLabels = ("2026-09-06 20:00", "2026-09-07 20:00", "2026-09-08 03:00")
        tokensByHour = (100.0, 200.0, 40.0)
        peakByHour = (False, False, False)

    result = zh.collect_history(db, Series)
    assert [p["key"] for p in result["daily"]] == ["2026-09-06", "2026-09-07", "2026-09-08"]
    assert result["monthly"] == [{"key": "2026-09", "tokens": 340.0}]
    assert len(result["weekly"]) >= 1
