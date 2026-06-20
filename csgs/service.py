from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from csgs.errors import SessionAlreadyExistsError, SessionNotFoundError
from csgs.models import Entry, Group, Session, Turn
from csgs.store import CSGSStore
from csgs.summary import generate_summary, summarize_session_increment


class SessionGraphService:
    def __init__(self, store: CSGSStore):
        self.store = store
        self.store.init_schema()

    def log_session(
        self,
        project: str | None,
        turns: list[dict[str, str]],
        parent_id: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
        title: str | None = None,
        codex_session_id: str | None = None,
    ) -> Session:
        if parent_id is not None and self.store.get_session(parent_id) is None:
            raise SessionNotFoundError(parent_id)

        chosen_id = session_id or self._new_session_id()
        if self.store.get_session(chosen_id) is not None:
            raise SessionAlreadyExistsError(chosen_id)

        self.store.create_session(
            Session(
                id=chosen_id,
                parent_id=parent_id,
                project=project,
                title=title,
                summary="",
                codex_session_id=codex_session_id,
                tags=tags or [],
                summary_turn_index=0,
            )
        )

        for turn in turns:
            self.append_turn(
                chosen_id,
                prompt=turn.get("prompt", ""),
                output=turn.get("output", ""),
            )

        return self.get_session(chosen_id)

    def append_turn(
        self,
        session_id: str,
        prompt: str,
        output: str,
        codex_session_id: str | None = None,
        codex_turn_id: str | None = None,
    ) -> Turn:
        session = self.get_session(session_id)
        if session.codex_session_id is None and codex_session_id is not None:
            session = self.store.update_session_codex_session_id(session_id, codex_session_id)
        if codex_turn_id is not None:
            existing = self.store.get_turn_by_codex_turn_id(codex_turn_id)
            if existing is not None:
                return existing
        turn_index = self.store.next_turn_index(session_id)
        turn = self.store.create_turn(
            Turn(
                id=self._new_turn_id(),
                session_id=session_id,
                turn_index=turn_index,
                prompt=prompt,
                output=output,
                summary=generate_summary(prompt, output),
                codex_session_id=session.codex_session_id,
                codex_turn_id=codex_turn_id,
            )
        )
        next_summary = summarize_session_increment(session.summary, turn.summary)
        self.store.update_session_summary(session_id, next_summary, turn.turn_index)
        return turn

    def record_summary(
        self,
        *,
        summary: str,
        cwd: str | None = None,
        project_id: str | None = None,
        codex_session_id: str | None = None,
        title: str | None = None,
        device_id: str | None = None,
        kind: str = "summary",
    ) -> Entry:
        resolved_project = project_id or derive_project(cwd)
        if not resolved_project:
            raise ValueError("project_id or cwd is required")
        session = self._ensure_record_session(
            project_id=resolved_project,
            codex_session_id=codex_session_id,
            title=title,
            device_id=device_id,
        )
        entry = self.store.create_entry(
            Entry(
                id=self._new_entry_id(),
                project_id=resolved_project,
                session_id=session.id,
                device_id=device_id,
                kind=kind,
                summary=summary,
            )
        )
        entry_count = len(self.store.list_entries(session.id))
        next_summary = summarize_session_increment(session.summary, summary)
        self.store.update_session_summary(session.id, next_summary, entry_count)
        return entry

    def ingest_codex_hook(self, event: str, payload: dict[str, object]) -> dict[str, object]:
        codex_session_id = self._payload_text(payload, "session_id")
        codex_turn_id = self._payload_text(payload, "turn_id")
        if codex_session_id is None:
            raise ValueError("Codex hook payload is missing session_id")
        if codex_turn_id is None and event != "SessionStart":
            raise ValueError("Codex hook payload is missing turn_id")

        cwd = self._payload_text(payload, "cwd")
        project = derive_project(cwd)
        session = self._ensure_codex_session(codex_session_id, project)

        if event == "UserPromptSubmit":
            prompt = self._payload_text(payload, "prompt") or ""
            if codex_turn_id is None:
                raise ValueError("Codex UserPromptSubmit payload is missing turn_id")
            self.store.upsert_pending_codex_turn(
                codex_session_id=codex_session_id,
                codex_turn_id=codex_turn_id,
                project=project,
                cwd=cwd,
                transcript_path=self._payload_text(payload, "transcript_path"),
                prompt=prompt,
            )
            return {"status": "pending", "session_id": session.id, "codex_session_id": codex_session_id}

        if event == "Stop":
            if codex_turn_id is None:
                raise ValueError("Codex Stop payload is missing turn_id")
            existing = self.store.get_turn_by_codex_turn_id(codex_turn_id)
            if existing is not None:
                return {
                    "status": "existing",
                    "session_id": existing.session_id,
                    "turn_id": existing.id,
                    "codex_turn_id": codex_turn_id,
                }
            pending = self.store.get_pending_codex_turn(codex_turn_id)
            prompt = ""
            if pending is not None:
                prompt = pending.get("prompt") or ""
            output = self._payload_text(payload, "last_assistant_message") or ""
            turn = self.append_turn(
                session.id,
                prompt=prompt,
                output=output,
                codex_session_id=codex_session_id,
                codex_turn_id=codex_turn_id,
            )
            self.store.delete_pending_codex_turn(codex_turn_id)
            return {
                "status": "recorded",
                "session_id": turn.session_id,
                "turn_id": turn.id,
                "codex_turn_id": codex_turn_id,
            }

        if event == "SessionStart":
            return {"status": "session", "session_id": session.id, "codex_session_id": codex_session_id}

        raise ValueError(f"unsupported Codex hook event: {event}")

    def fork_session(
        self,
        source_id: str,
        turns: list[dict[str, str]] | None = None,
        project: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
        codex_session_id: str | None = None,
    ) -> Session:
        source = self.get_session(source_id)
        return self.log_session(
            project=project if project is not None else source.project,
            title=title if title is not None else source.title,
            parent_id=source.id,
            tags=tags if tags is not None else source.tags,
            session_id=session_id,
            codex_session_id=codex_session_id,
            turns=turns or [],
        )

    def get_session(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def list_turns(self, session_id: str) -> list[Turn]:
        self.get_session(session_id)
        return self.store.list_turns(session_id)

    def list_entries(self, session_id: str) -> list[Entry]:
        self.get_session(session_id)
        return self.store.list_entries(session_id)

    def list_project_entries(self, project_id: str) -> list[Entry]:
        return self.store.list_project_entries(project_id)

    def add_group_project(self, group_id: str, project_id: str, name: str | None = None) -> Group:
        group = self.store.upsert_group(Group(id=group_id, name=name))
        self.store.add_group_project(group_id, project_id)
        return group

    def list_group_entries(self, group_id: str) -> list[Entry]:
        entries: list[Entry] = []
        for project_id in self.store.list_group_project_ids(group_id):
            entries.extend(self.store.list_project_entries(project_id))
        return entries

    def search_sessions(
        self,
        text: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> list[Session]:
        return self.store.search_sessions(text=text, tags=tags, project=project)

    def trace_session(self, session_id: str) -> str:
        target = self.get_session(session_id)
        root = self._find_session_root(target)
        lines = [root.id]
        lines.extend(self._render_session_children(root.id, prefix=""))
        return "\n".join(lines)

    def _new_session_id(self) -> str:
        while True:
            session_id = f"S_{uuid4().hex[:12]}"
            if self.store.get_session(session_id) is None:
                return session_id

    def _new_entry_id(self) -> str:
        while True:
            entry_id = f"E_{uuid4().hex[:12]}"
            if self.store.get_entry(entry_id) is None:
                return entry_id

    def _ensure_record_session(
        self,
        *,
        project_id: str,
        codex_session_id: str | None,
        title: str | None,
        device_id: str | None,
    ) -> Session:
        if codex_session_id is not None:
            existing = self.store.get_session_by_codex_session_id(codex_session_id)
            if existing is not None and existing.project == project_id:
                return existing
        session_id = (
            self._session_id_for_codex_session(codex_session_id)
            if codex_session_id
            else self._new_session_id()
        )
        if self.store.get_session(session_id) is not None:
            session_id = self._new_session_id()
        return self.store.create_session(
            Session(
                id=session_id,
                parent_id=None,
                project=project_id,
                title=title or project_id,
                summary="",
                codex_session_id=codex_session_id,
                tags=["csgs-entry"],
                summary_turn_index=0,
                device_id=device_id,
            )
        )

    def _ensure_codex_session(self, codex_session_id: str, project: str | None) -> Session:
        existing = self.store.get_session_by_codex_session_id(codex_session_id)
        if existing is not None:
            return existing
        session_id = self._session_id_for_codex_session(codex_session_id)
        if self.store.get_session(session_id) is not None:
            session_id = self._new_session_id()
        return self.log_session(
            project=project,
            title=project,
            tags=["codex-hook"],
            session_id=session_id,
            codex_session_id=codex_session_id,
            turns=[],
        )

    @staticmethod
    def _session_id_for_codex_session(codex_session_id: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9]+", "_", codex_session_id).strip("_")
        return f"S_codex_{sanitized[:80]}"

    @staticmethod
    def _payload_text(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        text = str(value)
        return text if text else None

    def _new_turn_id(self) -> str:
        while True:
            turn_id = f"T_{uuid4().hex[:12]}"
            if self.store.get_turn(turn_id) is None:
                return turn_id

    def _find_session_root(self, session: Session) -> Session:
        seen = {session.id}
        current = session
        while current.parent_id is not None:
            if current.parent_id in seen:
                break
            seen.add(current.parent_id)
            current = self.get_session(current.parent_id)
        return current

    def _render_session_children(self, parent_id: str, prefix: str) -> list[str]:
        children = self.store.get_session_children(parent_id)
        lines: list[str] = []
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix} {connector}{child.id}")
            extension = "    " if is_last else "│   "
            lines.extend(self._render_session_children(child.id, prefix=f"{prefix} {extension}"))
        return lines


def derive_project(cwd: str | None) -> str | None:
    if not cwd:
        return None
    if os.name != "nt" and _is_windows_absolute_path(cwd):
        return f"path:{_normalize_windows_path(cwd)}"
    path = Path(cwd).resolve()
    root = _git_output(cwd, "rev-parse", "--show-toplevel")
    if root:
        remote = _git_output(root, "remote", "get-url", "origin")
        normalized = _normalize_git_remote(remote)
        if normalized:
            return normalized
        return f"path:{Path(root).resolve()}"
    return f"path:{path}"


def _is_windows_absolute_path(value: str) -> bool:
    return len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] in {"\\", "/"}


def _normalize_windows_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def _git_output(cwd: str, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", cwd, *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _normalize_git_remote(remote: str | None) -> str | None:
    if not remote:
        return None
    value = remote.removesuffix(".git")
    if "://" in value:
        value = value.split("://", 1)[1]
        if "/" in value:
            host, path = value.split("/", 1)
            value = f"{host}:{path}"
    elif ":" in value:
        host, path = value.split(":", 1)
        if "@" in host:
            host = host.split("@", 1)[1]
        value = f"{host}:{path}"
    value = value.strip("/")
    if value.startswith("github.com:"):
        value = f"github:{value.removeprefix('github.com:')}"
    return value if value else None
