"""Zhipu Coding Plan usage — boundary layer: credentials and HTTP.

Everything that touches the outside world lives here: key resolution
(ADR-0004 order), region routing, and the GET requests against the two Zhipu
monitor hosts. Parsing of what comes back belongs to ``zhipu_collector``.
The API key is used to build Authorization headers only.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode

from zhipu_secure import read_json_bounded

REGION_BASE_URLS: Final[dict[str, str]] = {
    "cn": "https://open.bigmodel.cn",
    "intl": "https://api.z.ai",
}

QUOTA_PATH: Final = "/api/monitor/usage/quota/limit"
MODEL_USAGE_PATH: Final = "/api/monitor/usage/model-usage"
TOOL_USAGE_PATH: Final = "/api/monitor/usage/tool-usage"

HTTP_TIMEOUT_S: Final = 8.0
MAX_RESPONSE_BYTES: Final = 2_000_000
USER_AGENT: Final = "omarchy-zhipu-coding-usage"

ENV_KEY_ORDER: Final = ("ZHIPUAI_API_KEY", "ZAI_API_KEY", "GLM_API_KEY")
OPENCODE_AUTH_RELPATH: Final = (".local", "share", "opencode", "auth.json")
OPENCODE_CN_PROVIDERS: Final = ("zhipuai-coding-plan", "zhipu", "zhipuai")
OPENCODE_INTL_PROVIDERS: Final = ("zai-coding-plan", "zai", "z-ai", "z.ai")


class FetchError(Exception):
    """Typed fetch failure carrying a machine-readable code for the panel."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    # Monitor APIs never redirect legitimately; following one would forward
    # the Authorization header to whatever host the redirect names
    # (urllib rebuilds the request with all headers kept). Fail closed.
    def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any) -> None:
        raise FetchError("redirected")


_OPENER: Final = urllib.request.build_opener(_NoRedirectHandler)


@dataclass(frozen=True, slots=True)
class Credentials:
    key: str
    region: str
    source: str


def read_config(path: Path) -> dict[str, Any]:
    return read_json_bounded(path)


def _auth_entry_key(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for field in ("key", "apiKey", "api_key", "token"):
            value = entry.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def resolve_credentials(config: dict[str, Any], env: dict[str, str]) -> Credentials | None:
    """ADR-0004 order: environment, then the plugin's own config file.

    No third-party credential store is read at runtime; opencode users import
    their key once with ``--import-key``. An explicit ``region`` in the
    config overrides any inferred region.
    """
    configured_region = str(config.get("region") or "").strip().lower()

    for var in ENV_KEY_ORDER:
        value = env.get(var, "").strip()
        if value:
            inferred = "intl" if var == "ZAI_API_KEY" else "cn"
            region = configured_region if configured_region in REGION_BASE_URLS else inferred
            return Credentials(value, region, "env:" + var)

    config_key = str(config.get("apiKey") or "").strip()
    if config_key:
        region = configured_region if configured_region in REGION_BASE_URLS else "cn"
        return Credentials(config_key, region, "config-file")
    return None


def find_opencode_credentials() -> Credentials | None:
    """Explicit one-time import source; never consulted at runtime."""
    auth = read_config(Path.home().joinpath(*OPENCODE_AUTH_RELPATH))
    for providers, region in (
        (OPENCODE_CN_PROVIDERS, "cn"),
        (OPENCODE_INTL_PROVIDERS, "intl"),
    ):
        for provider in providers:
            value = _auth_entry_key(auth.get(provider)).strip()
            if value:
                return Credentials(value, region, "opencode:" + provider)
    return None


def fetch_json(
    base_url: str,
    path: str,
    credentials: Credentials,
    config: dict[str, Any],
    params: dict[str, str] | None = None,
) -> Any:
    """GET one monitor endpoint. Raw Authorization first, Bearer on 401."""
    url = base_url + path + (("?" + urlencode(params)) if params else "")

    def request(auth_header: str) -> urllib.request.Request:
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Authorization": auth_header,
        }
        org = str(config.get("organization") or "").strip()
        project = str(config.get("project") or "").strip()
        if org:
            headers["bigmodel-organization"] = org
        if project:
            headers["bigmodel-project"] = project
        return urllib.request.Request(url, headers=headers)

    for attempt, header in enumerate((credentials.key, "Bearer " + credentials.key)):
        try:
            with _OPENER.open(request(header), timeout=HTTP_TIMEOUT_S) as response:
                payload = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and attempt == 0:
                continue
            raise FetchError(f"http-{exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchError("unreachable") from exc
        except ValueError as exc:
            raise FetchError("bad-payload") from exc

        if isinstance(payload, dict) and payload.get("code") not in (None, 200, "200"):
            raise FetchError(f"api-{payload.get('code')}")
        return payload
    raise FetchError("http-401")


def usage_window_params(now: dt.datetime | None = None) -> dict[str, str]:
    """model/tool-usage are windowed; last 24 hours is the display contract."""
    now = now or dt.datetime.now().astimezone()
    fmt = "%Y-%m-%d %H:%M:%S"
    return {
        "startTime": (now - dt.timedelta(days=1)).strftime(fmt),
        "endTime": now.strftime(fmt),
    }
