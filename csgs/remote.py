from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from csgs.config import api_base


def ingest_codex_hook_remote(endpoint: str, event: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps({"event": event, "payload": payload}).encode("utf-8")
    request = Request(
        f"{api_base(endpoint)}/api/hooks/codex",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"remote CSGS hook ingest failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"remote CSGS hook ingest failed: {exc.reason}") from exc

    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("remote CSGS hook ingest returned a non-object JSON response")
    return parsed


def post_json(endpoint: str, path: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{api_base(endpoint)}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _send_json(request)


def get_json(endpoint: str, path: str, params: dict[str, str]) -> dict[str, object]:
    query = urlencode(params)
    request = Request(f"{api_base(endpoint)}{path}?{query}", method="GET")
    return _send_json(request)


def _send_json(request: Request) -> dict[str, object]:
    try:
        with urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"remote CSGS request failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"remote CSGS request failed: {exc.reason}") from exc
    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("remote CSGS returned a non-object JSON response")
    return parsed
