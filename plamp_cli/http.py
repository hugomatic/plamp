from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"API {status}: {detail}")
        self.status = status
        self.detail = detail


class NetworkError(RuntimeError):
    pass


def build_base_url(host: str | None, port: int | None, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")

    env_base_url = os.environ.get("PLAMP_BASE_URL", "").strip()
    if env_base_url:
        return env_base_url.rstrip("/")

    resolved_host = host or os.environ.get("PLAMP_HOST") or "127.0.0.1"
    resolved_port = port or int(os.environ.get("PLAMP_PORT") or "8000")
    return f"http://{resolved_host}:{resolved_port}"


def request_json(
    method: str,
    base_url: str,
    path: str,
    payload: Any | None = None,
    query: dict[str, Any] | None = None,
) -> Any:
    query_string = f"?{urlencode(query)}" if query else ""
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(f"{base_url}{path}{query_string}", data=data, method=method, headers=headers)
    try:
        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8").strip() or exc.reason
        raise ApiError(exc.code, detail) from exc
    except URLError as exc:
        raise NetworkError(str(exc.reason)) from exc
