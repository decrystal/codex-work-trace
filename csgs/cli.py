from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from csgs.codex_context import current_codex_session_id
from csgs.config import default_local_db_path, load_config, resolve_db_path
from csgs.errors import CSGSError
from csgs.installer import install_local, install_remote
from csgs.models import Entry, Session, Turn
from csgs.remote import ingest_codex_hook_remote
from csgs.service import SessionGraphService
from csgs.store import CSGSStore
from csgs.sync import sync_project_with_remote


DEFAULT_DB = ".csgs/csgs.sqlite3"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "install":
            if args.mode == "local":
                db_path = _install_db_path(args.install_db)
                result = install_local(
                    db_path=db_path,
                    runtime=args.runtime,
                    binary_path=args.binary_path,
                )
            else:
                result = install_remote(
                    endpoint=args.endpoint,
                    token=args.token,
                    runtime=args.runtime,
                    binary_path=args.binary_path,
                )
            _print_install_result(result)
            return 0

        if args.command in {"serve", "mcp-server"}:
            from csgs import mcp_server

            transport = "stdio" if args.command == "mcp-server" else args.transport
            host = "127.0.0.1" if args.command == "mcp-server" else args.host
            port = "8765" if args.command == "mcp-server" else str(args.port)
            forwarded = [
                    "--transport",
                    transport,
                    "--host",
                    host,
                    "--port",
                    port,
                    "--db",
                    str(resolve_db_path(args.db)),
            ]
            if getattr(args, "token", None):
                forwarded.extend(["--token", args.token])
            return mcp_server.main(forwarded)

        if args.command == "init":
            print(str(resolve_db_path(args.db)))
            return 0
        if args.command == "hook-ingest":
            payload = json.load(sys.stdin)
            if not isinstance(payload, dict):
                raise ValueError("hook payload must be a JSON object")
            result = _ingest_hook(args.event, payload, explicit_db=args.db)
            if args.print_result:
                _print_json(result)
            return 0

        store = CSGSStore(resolve_db_path(args.db))
        service = SessionGraphService(store)
        if args.command == "record-summary":
            entry = service.record_summary(
                summary=args.summary,
                cwd=args.cwd,
                project_id=args.project,
                codex_session_id=_resolve_codex_session_id(args.codex_session_id),
                title=args.title,
                device_id=args.device_id,
                kind=args.kind,
            )
            session = service.get_session(entry.session_id)
            result = {**_entry_to_dict(entry), "codex_session_id": session.codex_session_id}
            sync_result = _auto_sync_if_configured(store, entry.project_id, explicit_db=args.db)
            if sync_result is not None:
                result["sync"] = sync_result
            _print_json(result)
            return 0
        if args.command == "group-add-project":
            group = service.add_group_project(args.group_id, args.project_id, name=args.name)
            _print_json({"id": group.id, "name": group.name})
            return 0
        if args.command == "entry-list":
            if args.group:
                entries = service.list_group_entries(args.group)
            elif args.project:
                entries = service.list_project_entries(args.project)
            elif args.session_id:
                entries = service.list_entries(args.session_id)
            else:
                raise ValueError("entry-list requires --group, --project, or --session-id")
            _print_json([_entry_to_dict(entry) for entry in entries])
            return 0
        if args.command == "session-log":
            session = service.log_session(
                project=args.project,
                title=args.title,
                parent_id=args.parent_id,
                tags=_parse_tags(args.tags),
                session_id=args.id,
                codex_session_id=_resolve_codex_session_id(args.codex_session_id),
                turns=[_parse_turn(turn) for turn in args.turn],
            )
            _print_json(_session_to_dict(session))
            return 0
        if args.command == "turn-append":
            turn = service.append_turn(
                args.session_id,
                prompt=args.prompt,
                output=args.output,
                codex_session_id=_resolve_codex_session_id(args.codex_session_id),
            )
            _print_json(_turn_to_dict(turn))
            return 0
        if args.command == "session-fork":
            session = service.fork_session(
                args.source_id,
                project=args.project,
                title=args.title,
                tags=_parse_tags(args.tags),
                session_id=args.id,
                codex_session_id=_resolve_codex_session_id(args.codex_session_id),
                turns=[_parse_turn(turn) for turn in args.turn],
            )
            _print_json(_session_to_dict(session))
            return 0
        if args.command == "session-get":
            _print_json(_session_to_dict(service.get_session(args.id)))
            return 0
        if args.command == "session-trace":
            print(service.trace_session(args.id))
            return 0
        if args.command == "session-search":
            sessions = service.search_sessions(
                text=args.text,
                tags=_parse_tags(args.tags),
                project=args.project,
            )
            _print_json([_session_to_dict(session) for session in sessions])
            return 0
    except (CSGSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csgs")
    parser.add_argument("--db", default=os.environ.get("CSGS_DB"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--mode", choices=["local", "remote"], default="local")
    install_parser.add_argument("--endpoint")
    install_parser.add_argument("--runtime", choices=["auto", "binary", "dev-python"], default="auto")
    install_parser.add_argument("--bin", dest="binary_path")
    install_parser.add_argument("--db", dest="install_db")
    install_parser.add_argument("--token")

    subparsers.add_parser("mcp-server")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default="8765")
    serve_parser.add_argument("--token")

    record_parser = subparsers.add_parser("record-summary")
    record_parser.add_argument("--summary", required=True)
    record_parser.add_argument("--cwd")
    record_parser.add_argument("--project")
    record_parser.add_argument("--title")
    record_parser.add_argument("--codex-session-id")
    record_parser.add_argument("--device-id")
    record_parser.add_argument("--kind", default="summary")

    group_add_parser = subparsers.add_parser("group-add-project")
    group_add_parser.add_argument("group_id")
    group_add_parser.add_argument("project_id")
    group_add_parser.add_argument("--name")

    entry_list_parser = subparsers.add_parser("entry-list")
    entry_list_parser.add_argument("--group")
    entry_list_parser.add_argument("--project")
    entry_list_parser.add_argument("--session-id")

    session_log_parser = subparsers.add_parser("session-log")
    session_log_parser.add_argument("--id")
    session_log_parser.add_argument("--parent-id")
    session_log_parser.add_argument("--project")
    session_log_parser.add_argument("--title")
    session_log_parser.add_argument("--codex-session-id")
    session_log_parser.add_argument("--tags", default="")
    session_log_parser.add_argument(
        "--turn",
        action="append",
        required=True,
        help="Turn encoded as 'prompt|||output'. May be repeated.",
    )

    turn_append_parser = subparsers.add_parser("turn-append")
    turn_append_parser.add_argument("session_id")
    turn_append_parser.add_argument("--codex-session-id")
    turn_append_parser.add_argument("--prompt", required=True)
    turn_append_parser.add_argument("--output", required=True)

    session_fork_parser = subparsers.add_parser("session-fork")
    session_fork_parser.add_argument("source_id")
    session_fork_parser.add_argument("--id")
    session_fork_parser.add_argument("--project")
    session_fork_parser.add_argument("--title")
    session_fork_parser.add_argument("--codex-session-id")
    session_fork_parser.add_argument("--tags", default="")
    session_fork_parser.add_argument(
        "--turn",
        action="append",
        default=[],
        help="Turn encoded as 'prompt|||output'. May be repeated.",
    )

    session_get_parser = subparsers.add_parser("session-get")
    session_get_parser.add_argument("id")

    session_trace_parser = subparsers.add_parser("session-trace")
    session_trace_parser.add_argument("id")

    search_parser = subparsers.add_parser("session-search")
    search_parser.add_argument("--text")
    search_parser.add_argument("--project")
    search_parser.add_argument("--tags", default="")

    hook_ingest_parser = subparsers.add_parser("hook-ingest")
    hook_ingest_parser.add_argument("--event", required=True)
    hook_ingest_parser.add_argument("--print-result", action="store_true")

    return parser


def _parse_tags(tags: str | None) -> list[str] | None:
    if tags is None:
        return None
    parsed = [tag.strip() for tag in tags.split(",") if tag.strip()]
    return parsed or None


def _resolve_codex_session_id(value: str | None) -> str | None:
    if value:
        return value
    return current_codex_session_id()


def _session_to_dict(session: Session) -> dict[str, object]:
    return {
        "id": session.id,
        "parent_id": session.parent_id,
        "project": session.project,
        "codex_session_id": session.codex_session_id,
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
        "codex_session_id": turn.codex_session_id,
        "codex_turn_id": turn.codex_turn_id,
        "turn_index": turn.turn_index,
        "prompt": turn.prompt,
        "output": turn.output,
        "summary": turn.summary,
        "created_at": turn.created_at,
    }


def _entry_to_dict(entry: Entry) -> dict[str, object]:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "session_id": entry.session_id,
        "device_id": entry.device_id,
        "kind": entry.kind,
        "summary": entry.summary,
        "created_at": entry.created_at,
        "sync_state": entry.sync_state,
    }


def _parse_turn(value: str) -> dict[str, str]:
    if "|||" not in value:
        raise ValueError("turn must be encoded as 'prompt|||output'")
    prompt, output = value.split("|||", 1)
    return {"prompt": prompt, "output": output}


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _ingest_hook(event: str, payload: dict[str, object], *, explicit_db: str | None) -> dict[str, object]:
    if explicit_db or os.environ.get("CSGS_DB"):
        return SessionGraphService(CSGSStore(resolve_db_path(explicit_db))).ingest_codex_hook(event, payload)

    config = load_config()
    if config.mode == "remote":
        if not config.endpoint:
            raise ValueError("remote CSGS mode requires endpoint in ~/.csgs/config.toml")
        return ingest_codex_hook_remote(config.endpoint, event, payload)

    return SessionGraphService(CSGSStore(resolve_db_path())).ingest_codex_hook(event, payload)


def _auto_sync_if_configured(
    store: CSGSStore,
    project_id: str,
    *,
    explicit_db: str | None,
) -> dict[str, object] | None:
    if explicit_db or os.environ.get("CSGS_DB"):
        return None
    config = load_config()
    if config.mode != "remote" or not config.endpoint:
        return None
    try:
        return sync_project_with_remote(store, config.endpoint, project_id)
    except ValueError as exc:
        return {"error": str(exc)}


def _install_db_path(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    env_db = os.environ.get("CSGS_DB")
    if env_db:
        return Path(env_db).expanduser()
    return default_local_db_path()


def _print_install_result(result: dict[str, str]) -> None:
    print(f"CSGS {result['mode']} install complete")
    print(f"Runtime: {result['runtime']}")
    if result.get("binary_path"):
        print(f"CSGS binary: {result['binary_path']}")
    if result.get("endpoint"):
        print(f"Endpoint: {result['endpoint']}")
    if result.get("mcp_endpoint"):
        print(f"MCP endpoint: {result['mcp_endpoint']}")
    print(f"CSGS config: {result['csgs_config_path']}")
    if result.get("codex_config_path"):
        print(f"Codex config: {result['codex_config_path']}")
    if result.get("db_path"):
        print(f"SQLite DB: {result['db_path']}")
    if result.get("mcp_configured"):
        print("Codex MCP: configured")
    if result.get("token_configured"):
        print("Token: configured")
    print("Default path is MCP-first. Hooks are not installed by this command.")


if __name__ == "__main__":
    raise SystemExit(main())
