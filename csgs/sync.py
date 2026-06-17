from __future__ import annotations

from typing import Any

from csgs.models import Run
from csgs.store import RunStore


def export_project(store: RunStore, project: str) -> dict[str, object]:
    return {
        "project": project,
        "runs": [run_to_dict(run) for run in store.list_project_runs(project)],
    }


def import_runs(store: RunStore, payload: dict[str, object]) -> dict[str, int]:
    imported = 0
    skipped = 0
    for item in payload.get("runs", []):
        run_data = _require_dict(item)
        run_id = str(run_data["id"])
        if store.get_run(run_id) is not None:
            skipped += 1
            continue
        store.create_run(run_from_dict(run_data))
        imported += 1
    return {"imported": imported, "skipped": skipped}


def run_to_dict(run: Run) -> dict[str, object]:
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


def run_from_dict(data: dict[str, Any]) -> Run:
    return Run(
        id=str(data["id"]),
        parent_id=_optional_str(data.get("parent_id")),
        project=_optional_str(data.get("project")),
        prompt=str(data.get("prompt", "")),
        output=str(data.get("output", "")),
        summary=str(data.get("summary", "")),
        tags=_tags(data.get("tags")),
        created_at=_optional_str(data.get("created_at")),
        device_id=_optional_str(data.get("device_id")),
        updated_at=_optional_str(data.get("updated_at")),
        sync_state=_optional_str(data.get("sync_state")) or "imported",
    )


def _require_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("run payload items must be objects")
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
