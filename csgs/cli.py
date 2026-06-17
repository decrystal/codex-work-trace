from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from csgs.errors import CSGSError
from csgs.models import Run
from csgs.service import SessionGraphService
from csgs.store import RunStore


DEFAULT_DB = ".csgs/csgs.sqlite3"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    service = SessionGraphService(RunStore(args.db))

    try:
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
    }


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
