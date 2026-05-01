from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HTTP_TIMEOUT_SECONDS = 10


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"API {status}: {detail}")
        self.status = status
        self.detail = detail


class NetworkError(RuntimeError):
    pass


def _clean_error_detail(raw_body: bytes, fallback: str) -> str:
    raw_text = raw_body.decode("utf-8", errors="replace").strip()
    if not raw_text:
        return fallback

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text

    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            messages: list[str] = []
            for item in detail:
                if isinstance(item, dict):
                    message = item.get("msg")
                    if isinstance(message, str):
                        messages.append(message)
                        continue
                messages.append(str(item))
            return "; ".join(messages) if messages else str(detail)
        return str(detail)

    return raw_text


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
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = _clean_error_detail(exc.read(), str(exc.reason))
        raise ApiError(exc.code, detail) from exc
    except URLError as exc:
        raise NetworkError(str(exc.reason)) from exc


def download_bytes(base_url: str, path: str) -> bytes:
    request = Request(f"{base_url}{path}", method="GET")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    except HTTPError as exc:
        detail = _clean_error_detail(exc.read(), str(exc.reason))
        raise ApiError(exc.code, detail) from exc
    except URLError as exc:
        raise NetworkError(str(exc.reason)) from exc
