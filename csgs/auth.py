from __future__ import annotations

import hmac
import json
import os
from urllib.parse import parse_qs


PROTECTED_PATHS = ("/api", "/mcp", "/ui")


class CSGSTokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        expected = configured_token()
        path = str(scope.get("path", ""))
        if not expected or not _is_protected_path(path) or path == "/health":
            await self.app(scope, receive, send)
            return

        if request_has_token(scope, expected):
            await self.app(scope, receive, send)
            return

        await _send_unauthorized(send, path)


def configured_token() -> str | None:
    token = os.environ.get("CSGS_TOKEN", "").strip()
    return token or None


def request_has_token(scope, expected: str) -> bool:
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    candidates = []
    authorization = headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        candidates.append(authorization[7:].strip())
    if headers.get("x-csgs-token"):
        candidates.append(headers["x-csgs-token"].strip())

    query = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="replace"))
    candidates.extend(value for value in query.get("token", []) if value)

    return any(hmac.compare_digest(candidate, expected) for candidate in candidates)


def _is_protected_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PROTECTED_PATHS)


async def _send_unauthorized(send, path: str) -> None:
    if path == "/ui" or path.startswith("/ui/"):
        body = b"Unauthorized"
        content_type = b"text/plain; charset=utf-8"
    else:
        body = json.dumps({"error": "unauthorized"}).encode("utf-8")
        content_type = b"application/json"
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", content_type),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
