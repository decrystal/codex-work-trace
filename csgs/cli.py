from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from csgs.errors import CSGSError
from csgs.models import Run, Session, Turn
from csgs.service import SessionGraphService
from csgs.store import RunStore


DEFAULT_DB = ".csgs/csgs.sqlite3"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "serve":
            from csgs import mcp_server

            return mcp_server.main(
                [
                    "--transport",
                    args.transport,
                    "--host",
                    args.host,
                    "--port",
                    str(args.port),
                    "--db",
                    args.db,
                ]
            )

        service = SessionGraphService(RunStore(args.db))

        if args.command == "init":
            print(str(Path(args.db)))
            return 0
        if args.command == "log":
            run = service.log_run(
                prompt=args.prompt,
                output=args.output,
                parent_id=args.parent_id,
                project=args.project,
                tags=_parse_tags(args.tags),
                run_id=args.id,
            )
            _print_json(_run_to_dict(run))
            return 0
        if args.command == "get":
            _print_json(_run_to_dict(service.get_run(args.id)))
            return 0
        if args.command == "fork":
            run = service.fork_run(
                source_id=args.source_id,
                prompt=args.prompt,
                output=args.output,
                project=args.project,
                tags=_parse_tags(args.tags),
                run_id=args.id,
            )
            _print_json(_run_to_dict(run))
            return 0
        if args.command == "trace":
            print(service.trace_run(args.id))
            return 0
        if args.command == "search":
            runs = service.search_runs(
                text=args.text,
                tags=_parse_tags(args.tags),
                project=args.project,
            )
            _print_json([_run_to_dict(run) for run in runs])
            return 0
        if args.command == "session-log":
            session = service.log_session(
                project=args.project,
                title=args.title,
                parent_id=args.parent_id,
                tags=_parse_tags(args.tags),
                session_id=args.id,
                turns=[_parse_turn(turn) for turn in args.turn],
            )
            _print_json(_session_to_dict(session))
            return 0
        if args.command == "turn-append":
            turn = service.append_turn(args.session_id, prompt=args.prompt, output=args.output)
            _print_json(_turn_to_dict(turn))
            return 0
        if args.command == "session-get":
            _print_json(_session_to_dict(service.get_session(args.id)))
            return 0
        if args.command == "session-trace":
            print(service.trace_session(args.id))
            return 0
    except CSGSError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csgs")
    parser.add_argument("--db", default=os.environ.get("CSGS_DB", DEFAULT_DB))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--id")
    log_parser.add_argument("--parent-id")
    log_parser.add_argument("--project")
    log_parser.add_argument("--tags", default="")
    log_parser.add_argument("--prompt", required=True)
    log_parser.add_argument("--output", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("id")

    fork_parser = subparsers.add_parser("fork")
    fork_parser.add_argument("source_id")
    fork_parser.add_argument("--id")
    fork_parser.add_argument("--project")
    fork_parser.add_argument("--tags", default="")
    fork_parser.add_argument("--prompt")
    fork_parser.add_argument("--output")

    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("id")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--text")
    search_parser.add_argument("--project")
    search_parser.add_argument("--tags", default="")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default="8765")

    session_log_parser = subparsers.add_parser("session-log")
    session_log_parser.add_argument("--id")
    session_log_parser.add_argument("--parent-id")
    session_log_parser.add_argument("--project")
    session_log_parser.add_argument("--title")
    session_log_parser.add_argument("--tags", default="")
    session_log_parser.add_argument(
        "--turn",
        action="append",
        required=True,
        help="Turn encoded as 'prompt|||output'. May be repeated.",
    )

    turn_append_parser = subparsers.add_parser("turn-append")
    turn_append_parser.add_argument("session_id")
    turn_append_parser.add_argument("--prompt", required=True)
    turn_append_parser.add_argument("--output", required=True)

    session_get_parser = subparsers.add_parser("session-get")
    session_get_parser.add_argument("id")

    session_trace_parser = subparsers.add_parser("session-trace")
    session_trace_parser.add_argument("id")

    return parser


def _parse_tags(tags: str | None) -> list[str] | None:
    if tags is None:
        return None
    parsed = [tag.strip() for tag in tags.split(",") if tag.strip()]
    return parsed or None


def _run_to_dict(run: Run) -> dict[str, object]:
    return {
        "id": run.id,
        "parent_id": run.parent_id,
        "project": run.project,
        "prompt": run.prompt,
        "output": run.output,
        "summary": run.summary,
        "tags": run.tags,
        "created_at": run.created_at,
        "device_id": run.device_id,
        "updated_at": run.updated_at,
        "sync_state": run.sync_state,
    }


def _session_to_dict(session: Session) -> dict[str, object]:
    return {
        "id": session.id,
        "parent_id": session.parent_id,
        "project": session.project,
        "title": session.title,
        "summary": session.summary,
        "tags": session.tags,
        "summary_turn_index": session.summary_turn_index,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "device_id": session.device_id,
        "sync_state": session.sync_state,
    }


def _turn_to_dict(turn: Turn) -> dict[str, object]:
    return {
        "id": turn.id,
        "session_id": turn.session_id,
        "turn_index": turn.turn_index,
        "prompt": turn.prompt,
        "output": turn.output,
        "summary": turn.summary,
        "created_at": turn.created_at,
    }


def _parse_turn(value: str) -> dict[str, str]:
    if "|||" not in value:
        raise ValueError("turn must be encoded as 'prompt|||output'")
    prompt, output = value.split("|||", 1)
    return {"prompt": prompt, "output": output}


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
