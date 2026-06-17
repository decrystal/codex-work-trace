from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from csgs.cli import DEFAULT_DB, _run_to_dict
from csgs.models import Run
from csgs.service import SessionGraphService
from csgs.store import RunStore


INSTRUCTIONS = (
    "CSGS records Codex or LLM coding assistant turns as local run nodes. "
    "Use log_run after a meaningful assistant turn; it generates the summary automatically. "
    "parent_id is an origin reference only, not an execution dependency."
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


def create_mcp_app():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install MCP support with: python -m pip install -e '.[mcp]'") from exc

    app = FastMCP("csgs", instructions=INSTRUCTIONS)

    app.tool()(log_run)
    app.tool()(get_run)
    app.tool()(trace_run)
    app.tool()(fork_run)

    return app


def main() -> int:
    try:
        app = create_mcp_app()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    app.run()
    return 0


def _service() -> SessionGraphService:
    return SessionGraphService(RunStore(_db_path()))


def _db_path() -> Path:
    return Path(os.environ.get("CSGS_DB", DEFAULT_DB))


def _as_json(value: Run | dict[str, object] | list[dict[str, object]] | str) -> str:
    if isinstance(value, Run):
        value = _run_to_dict(value)
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
