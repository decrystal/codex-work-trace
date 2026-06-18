from __future__ import annotations

from typing import Any

from csgs.models import Entry, Session, Turn
from csgs.remote import get_json, post_json
from csgs.store import CSGSStore


def export_project(store: CSGSStore, project: str) -> dict[str, object]:
    sessions = store.list_project_sessions(project)
    return {
        "project": project,
        "sessions": [session_to_dict(session) for session in sessions],
        "turns": [
            turn_to_dict(turn)
            for session in sessions
            for turn in store.list_turns(session.id)
        ],
        "entries": [entry_to_dict(entry) for entry in store.list_project_entries(project)],
    }


def import_sessions(store: CSGSStore, payload: dict[str, object]) -> dict[str, int]:
    imported = 0
    skipped = 0

    for item in payload.get("sessions", []):
        session_data = _require_dict(item)
        session_id = str(session_data["id"])
        if store.get_session(session_id) is not None:
            skipped += 1
            continue
        store.create_session(session_from_dict(session_data))
        imported += 1

    for item in payload.get("turns", []):
        turn_data = _require_dict(item)
        turn_id = str(turn_data["id"])
        if store.get_turn(turn_id) is not None:
            skipped += 1
            continue
        store.create_turn(turn_from_dict(turn_data))
        imported += 1

    for item in payload.get("entries", []):
        entry_data = _require_dict(item)
        entry_id = str(entry_data["id"])
        if store.get_entry(entry_id) is not None:
            skipped += 1
            continue
        store.create_entry(entry_from_dict(entry_data))
        imported += 1

    return {"imported": imported, "skipped": skipped}


def sync_project_with_remote(store: CSGSStore, endpoint: str, project: str) -> dict[str, object]:
    pushed = post_json(endpoint, "/api/sync/import", export_project(store, project))
    remote_payload = get_json(endpoint, "/api/sync/export", {"project": project})
    pulled = import_sessions(store, remote_payload)
    return {"pushed": pushed, "pulled": pulled}


def session_to_dict(session: Session) -> dict[str, object]:
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


def turn_to_dict(turn: Turn) -> dict[str, object]:
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


def entry_to_dict(entry: Entry) -> dict[str, object]:
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


def session_from_dict(data: dict[str, Any]) -> Session:
    return Session(
        id=str(data["id"]),
        parent_id=_optional_str(data.get("parent_id")),
        project=_optional_str(data.get("project")),
        codex_session_id=_optional_str(data.get("codex_session_id") or data.get("codexSessionId")),
        title=_optional_str(data.get("title")),
        summary=str(data.get("summary", "")),
        tags=_tags(data.get("tags")),
        summary_turn_index=int(data.get("summary_turn_index") or 0),
        created_at=_optional_str(data.get("created_at")),
        updated_at=_optional_str(data.get("updated_at")),
        device_id=_optional_str(data.get("device_id")),
        sync_state=_optional_str(data.get("sync_state")) or "imported",
    )


def turn_from_dict(data: dict[str, Any]) -> Turn:
    return Turn(
        id=str(data["id"]),
        session_id=str(data["session_id"]),
        codex_session_id=_optional_str(data.get("codex_session_id") or data.get("codexSessionId")),
        codex_turn_id=_optional_str(data.get("codex_turn_id") or data.get("codexTurnId")),
        turn_index=int(data["turn_index"]),
        prompt=str(data.get("prompt", "")),
        output=str(data.get("output", "")),
        summary=str(data.get("summary", "")),
        created_at=_optional_str(data.get("created_at")),
    )


def entry_from_dict(data: dict[str, Any]) -> Entry:
    return Entry(
        id=str(data["id"]),
        project_id=str(data["project_id"]),
        session_id=str(data["session_id"]),
        device_id=_optional_str(data.get("device_id")),
        kind=str(data.get("kind", "summary")),
        summary=str(data.get("summary", "")),
        created_at=_optional_str(data.get("created_at")),
        sync_state=_optional_str(data.get("sync_state")) or "imported",
    )


def _require_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("payload items must be objects")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if isinstance(value, list):
        return [str(tag) for tag in value]
    raise ValueError("tags must be a list or comma-separated string")
