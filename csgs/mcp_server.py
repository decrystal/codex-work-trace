from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import unquote, urlparse

from csgs.auth import CSGSTokenAuthMiddleware
from csgs.service import SessionGraphService, derive_project
from csgs.store import CSGSStore
from csgs.sync import entry_to_dict, session_to_dict, turn_to_dict

try:  # Keep importing this module possible before the optional MCP extra is installed.
    from mcp.server.fastmcp import Context as MCPContext
except ModuleNotFoundError:  # pragma: no cover - exercised only without the mcp extra.
    class MCPContext:  # type: ignore[no-redef]
        pass


INSTRUCTIONS = (
    "CSGS records Codex coding sessions as append-only summary entries. "
    "When the user says '用 CSGS 总结', 'record this session', or asks for a CSGS summary, "
    "first call get_runtime_context, then call record_current_session_summary with a concise 3-5 sentence summary. "
    "Use record_current_session_summary for current-chat checkpoints; it derives cwd/project_id from MCP roots when possible. "
    "If Codex thread id appears in MCP _meta, pass it as codex_session_id; otherwise leave it null. "
    "Do not treat the MCP transport session id as the Codex thread id. "
    "Use list_project_entries/list_group_entries/search_sessions for history queries. "
    "parent_id is an origin reference only, not an execution dependency."
)

DEFAULT_DB = ".csgs/csgs.sqlite3"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MCP_PATH = "/mcp"


async def log_session(
    project: str | None,
    turns: list[dict[str, str]],
    parent_id: str | None = None,
    tags: list[str] | None = None,
    session_id: str | None = None,
    title: str | None = None,
    codex_session_id: str | None = None,
) -> dict[str, object]:
    session = _service().log_session(
        project=project,
        turns=turns,
        parent_id=parent_id,
        tags=tags,
        session_id=session_id,
        title=title,
        codex_session_id=codex_session_id,
    )
    return session_to_dict(session)


async def append_turn(
    session_id: str,
    prompt: str,
    output: str,
    codex_session_id: str | None = None,
) -> dict[str, object]:
    return turn_to_dict(
        _service().append_turn(
            session_id,
            prompt=prompt,
            output=output,
            codex_session_id=codex_session_id,
        )
    )


async def fork_session(
    id: str,
    turns: list[dict[str, str]] | None = None,
    project: str | None = None,
    tags: list[str] | None = None,
    session_id: str | None = None,
    title: str | None = None,
    codex_session_id: str | None = None,
) -> dict[str, object]:
    session = _service().fork_session(
        source_id=id,
        turns=turns or [],
        project=project,
        title=title,
        tags=tags,
        session_id=session_id,
        codex_session_id=codex_session_id,
    )
    return session_to_dict(session)


async def get_session(id: str) -> dict[str, object]:
    return session_to_dict(_service().get_session(id))


async def trace_session(id: str) -> str:
    return _service().trace_session(id)


async def search_sessions(
    text: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
) -> list[dict[str, object]]:
    return [
        session_to_dict(session)
        for session in _service().search_sessions(text=text, tags=tags, project=project)
    ]


async def record_summary(
    summary: str,
    project_id: str | None = None,
    cwd: str | None = None,
    codex_session_id: str | None = None,
    title: str | None = None,
    device_id: str | None = None,
    kind: str = "summary",
) -> dict[str, object]:
    entry = _service().record_summary(
        summary=summary,
        project_id=project_id,
        cwd=cwd,
        codex_session_id=codex_session_id,
        title=title,
        device_id=device_id,
        kind=kind,
    )
    return entry_to_dict(entry)


async def get_runtime_context(ctx: MCPContext | None = None) -> dict[str, object]:
    """Return CSGS runtime context visible through MCP without mutating storage."""
    roots = await _list_roots(ctx)
    cwd = _first_root_path(roots)
    project_id = derive_project(cwd) if cwd else None
    meta = _request_meta(ctx)
    return {
        "db_path": str(_db_path()),
        "cwd": cwd,
        "project_id": project_id,
        "codex_session_id": _codex_session_id_from_meta(meta),
        "roots": roots,
        "mcp_request": {
            "request_id": _request_id(ctx),
            "client_id": _client_id(ctx, meta),
            "meta": meta,
        },
    }


async def record_current_session_summary(
    summary: str,
    codex_session_id: str | None = None,
    project_id: str | None = None,
    cwd: str | None = None,
    title: str | None = None,
    device_id: str | None = None,
    kind: str = "summary",
    ctx: MCPContext | None = None,
) -> dict[str, object]:
    """Record a summary checkpoint for the current Codex session using MCP context fallbacks."""
    runtime = await get_runtime_context(ctx)
    resolved_codex_session_id = codex_session_id or _optional_str(runtime.get("codex_session_id"))
    resolved_project_id = project_id or _optional_str(runtime.get("project_id"))
    resolved_cwd = cwd or _optional_str(runtime.get("cwd"))
    entry = _service().record_summary(
        summary=summary,
        project_id=resolved_project_id,
        cwd=resolved_cwd,
        codex_session_id=resolved_codex_session_id,
        title=title,
        device_id=device_id,
        kind=kind,
    )
    session = _service().get_session(entry.session_id)
    return {
        **entry_to_dict(entry),
        "codex_session_id": session.codex_session_id,
        "db_path": str(_db_path()),
        "runtime_context": runtime,
    }


async def list_project_entries(project_id: str) -> list[dict[str, object]]:
    return [entry_to_dict(entry) for entry in _service().list_project_entries(project_id)]


async def list_group_entries(group_id: str) -> list[dict[str, object]]:
    return [entry_to_dict(entry) for entry in _service().list_group_entries(group_id)]


def create_mcp_app(host: str | None = None, port: int | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install MCP support with: python -m pip install -e '.[mcp]'") from exc

    CSGSStore(_db_path()).init_schema()

    app = FastMCP(
        "csgs",
        instructions=INSTRUCTIONS,
        host=host or os.environ.get("CSGS_HOST", DEFAULT_HOST),
        port=port or _env_int("CSGS_PORT", DEFAULT_PORT),
        streamable_http_path=DEFAULT_MCP_PATH,
    )

    app.tool()(log_session)
    app.tool()(append_turn)
    app.tool()(fork_session)
    app.tool()(get_session)
    app.tool()(trace_session)
    app.tool()(search_sessions)
    app.tool()(record_summary)
    app.tool()(get_runtime_context)
    app.tool()(record_current_session_summary)
    app.tool()(list_project_entries)
    app.tool()(list_group_entries)

    from csgs.http_api import register_api_routes

    register_api_routes(app)
    _wrap_streamable_http_app_with_auth(app)
    return app


def _wrap_streamable_http_app_with_auth(app):
    original = app.streamable_http_app

    def streamable_http_app():
        starlette_app = original()
        starlette_app.add_middleware(CSGSTokenAuthMiddleware)
        return starlette_app

    app.streamable_http_app = streamable_http_app


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.db:
        os.environ["CSGS_DB"] = args.db
    os.environ["CSGS_HOST"] = args.host
    os.environ["CSGS_PORT"] = str(args.port)
    if args.token:
        os.environ["CSGS_TOKEN"] = args.token

    try:
        app = create_mcp_app(host=args.host, port=args.port)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        app.run(transport=args.transport)
        return 0
    except KeyboardInterrupt:
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m csgs.mcp_server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default=os.environ.get("CSGS_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=_env_int("CSGS_PORT", DEFAULT_PORT))
    parser.add_argument("--db", default=os.environ.get("CSGS_DB"))
    parser.add_argument("--token", default=os.environ.get("CSGS_TOKEN"))
    return parser


def _service() -> SessionGraphService:
    return SessionGraphService(CSGSStore(_db_path()))


def _db_path() -> Path:
    return Path(os.environ.get("CSGS_DB", DEFAULT_DB))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


async def _list_roots(ctx: MCPContext | None) -> list[dict[str, object]]:
    if ctx is None:
        return []
    request_context = getattr(ctx, "request_context", None)
    session = getattr(request_context, "session", None)
    if session is None or not hasattr(session, "list_roots"):
        return []
    try:
        result = await session.list_roots()
    except Exception:
        return []
    roots = getattr(result, "roots", []) or []
    return [
        {
            "uri": str(getattr(root, "uri", "")),
            "name": getattr(root, "name", None),
        }
        for root in roots
        if getattr(root, "uri", None)
    ]


def _first_root_path(roots: list[dict[str, object]]) -> str | None:
    for root in roots:
        path = _file_uri_to_path(_optional_str(root.get("uri")))
        if path:
            return path
    return None


def _file_uri_to_path(uri: str | None) -> str | None:
    if not uri:
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return str(Path(unquote(parsed.path)).resolve())


def _request_meta(ctx: MCPContext | None) -> dict[str, object]:
    request_context = getattr(ctx, "request_context", None)
    meta = getattr(request_context, "meta", None)
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return {str(key): value for key, value in meta.items()}
    if hasattr(meta, "model_dump"):
        dumped = meta.model_dump(by_alias=True, exclude_none=True)
        return {str(key): value for key, value in dumped.items()}
    values: dict[str, object] = {}
    for key in (
        "client_id",
        "codex_session_id",
        "codexSessionId",
        "codex_thread_id",
        "codexThreadId",
        "thread_id",
        "threadId",
        "session_id",
        "sessionId",
    ):
        if hasattr(meta, key):
            value = getattr(meta, key)
            if value is not None:
                values[key] = value
    return values


def _codex_session_id_from_meta(meta: dict[str, object]) -> str | None:
    for key in (
        "codex_session_id",
        "codexSessionId",
        "codex_thread_id",
        "codexThreadId",
        "thread_id",
        "threadId",
    ):
        value = _optional_str(meta.get(key))
        if value:
            return value
    return None


def _request_id(ctx: MCPContext | None) -> str | None:
    request_id = getattr(ctx, "request_id", None)
    if request_id is not None:
        return str(request_id)
    request_context = getattr(ctx, "request_context", None)
    value = getattr(request_context, "request_id", None)
    return str(value) if value is not None else None


def _client_id(ctx: MCPContext | None, meta: dict[str, object]) -> str | None:
    value = getattr(ctx, "client_id", None)
    if value is not None:
        return str(value)
    return _optional_str(meta.get("client_id"))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


if __name__ == "__main__":
    raise SystemExit(main())
