from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from csgs.cli import DEFAULT_DB, _run_to_dict
from csgs.models import Run
from csgs.service import SessionGraphService
from csgs.store import RunStore
from csgs.sync import session_to_dict, turn_to_dict


INSTRUCTIONS = (
    "CSGS records full Codex or LLM coding assistant sessions as graph nodes. "
    "Use log_session for a whole chat and append_turn for later user/assistant turns; "
    "append_turn updates session summary incrementally from the old summary plus the new turn summary. "
    "parent_id is a session origin reference only, not an execution dependency."
)


async def log_run(
    prompt: str,
    output: str,
    parent_id: str | None = None,
    project: str | None = None,
    tags: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    run = _service().log_run(
        prompt=prompt,
        output=output,
        parent_id=parent_id,
        project=project,
        tags=tags,
        run_id=run_id,
    )
    return _run_to_dict(run)


async def get_run(id: str) -> dict[str, object]:
    return _run_to_dict(_service().get_run(id))


async def trace_run(id: str) -> str:
    return _service().trace_run(id)


async def fork_run(
    id: str,
    prompt: str | None = None,
    output: str | None = None,
    project: str | None = None,
    tags: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    run = _service().fork_run(
        source_id=id,
        prompt=prompt,
        output=output,
        project=project,
        tags=tags,
        run_id=run_id,
    )
    return _run_to_dict(run)


async def log_session(
    project: str | None,
    turns: list[dict[str, str]],
    parent_id: str | None = None,
    tags: list[str] | None = None,
    session_id: str | None = None,
    title: str | None = None,
) -> dict[str, object]:
    session = _service().log_session(
        project=project,
        turns=turns,
        parent_id=parent_id,
        tags=tags,
        session_id=session_id,
        title=title,
    )
    return session_to_dict(session)


async def append_turn(session_id: str, prompt: str, output: str) -> dict[str, object]:
    return turn_to_dict(_service().append_turn(session_id, prompt=prompt, output=output))


async def get_session(id: str) -> dict[str, object]:
    return session_to_dict(_service().get_session(id))


async def trace_session(id: str) -> str:
    return _service().trace_session(id)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MCP_PATH = "/mcp"


def create_mcp_app(host: str | None = None, port: int | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install MCP support with: python -m pip install -e '.[mcp]'") from exc

    app = FastMCP(
        "csgs",
        instructions=INSTRUCTIONS,
        host=host or os.environ.get("CSGS_HOST", DEFAULT_HOST),
        port=port or _env_int("CSGS_PORT", DEFAULT_PORT),
        streamable_http_path=DEFAULT_MCP_PATH,
    )

    app.tool()(log_run)
    app.tool()(get_run)
    app.tool()(trace_run)
    app.tool()(fork_run)
    app.tool()(log_session)
    app.tool()(append_turn)
    app.tool()(get_session)
    app.tool()(trace_session)

    from csgs.http_api import register_api_routes

    register_api_routes(app)

    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.db:
        os.environ["CSGS_DB"] = args.db
    os.environ["CSGS_HOST"] = args.host
    os.environ["CSGS_PORT"] = str(args.port)

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
    return parser


def _service() -> SessionGraphService:
    return SessionGraphService(RunStore(_db_path()))


def _db_path() -> Path:
    return Path(os.environ.get("CSGS_DB", DEFAULT_DB))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


def _as_json(value: Run | dict[str, object] | list[dict[str, object]] | str) -> str:
    if isinstance(value, Run):
        value = _run_to_dict(value)
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
