from __future__ import annotations

from json import JSONDecodeError
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from csgs.errors import CSGSError, SessionNotFoundError
from csgs.mcp_server import _db_path, _service
from csgs.sync import entry_to_dict, export_project, import_sessions, session_to_dict, turn_to_dict
from csgs.ui import render_ui


def register_api_routes(app: Any) -> None:
    @app.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok", "db": str(_db_path())})

    @app.custom_route("/ui", methods=["GET"])
    async def ui(request: Request) -> Response:
        return HTMLResponse(render_ui())

    @app.custom_route("/api/sessions", methods=["POST"])
    async def create_session(request: Request) -> Response:
        try:
            data = await _json_body(request)
            session = _service().log_session(
                project=_optional_str(data.get("project")),
                title=_optional_str(data.get("title")),
                parent_id=_optional_str(data.get("parent_id")),
                tags=_tags(data.get("tags")),
                session_id=_optional_str(data.get("id") or data.get("session_id")),
                codex_session_id=_codex_session_id(data),
                turns=_turns(data.get("turns", [])),
            )
            return JSONResponse(session_to_dict(session))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/sessions/{session_id}", methods=["GET"])
    async def get_session(request: Request) -> Response:
        try:
            return JSONResponse(session_to_dict(_service().get_session(request.path_params["session_id"])))
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/sessions/{session_id}/fork", methods=["POST"])
    async def fork_session(request: Request) -> Response:
        try:
            data = await _json_body(request)
            session = _service().fork_session(
                request.path_params["session_id"],
                project=_optional_str(data.get("project")),
                title=_optional_str(data.get("title")),
                tags=_tags(data.get("tags")),
                session_id=_optional_str(data.get("id") or data.get("session_id")),
                codex_session_id=_codex_session_id(data),
                turns=_turns(data.get("turns", [])),
            )
            return JSONResponse(session_to_dict(session))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/sessions/{session_id}/turns", methods=["GET"])
    async def list_session_turns(request: Request) -> Response:
        try:
            turns = _service().list_turns(request.path_params["session_id"])
            return JSONResponse([turn_to_dict(turn) for turn in turns])
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/sessions/{session_id}/turns", methods=["POST"])
    async def append_session_turn(request: Request) -> Response:
        try:
            data = await _json_body(request)
            turn = _service().append_turn(
                request.path_params["session_id"],
                prompt=str(data.get("prompt", "")),
                output=str(data.get("output", "")),
                codex_session_id=_codex_session_id(data) or _optional_str(request.headers.get("x-codex-session-id")),
            )
            return JSONResponse(turn_to_dict(turn))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/sessions/{session_id}/trace", methods=["GET"])
    async def trace_session(request: Request) -> Response:
        try:
            return PlainTextResponse(_service().trace_session(request.path_params["session_id"]))
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/search", methods=["GET"])
    async def search_sessions(request: Request) -> Response:
        sessions = _service().search_sessions(
            text=request.query_params.get("text"),
            tags=_tags(request.query_params.get("tags")),
            project=request.query_params.get("project"),
        )
        return JSONResponse([session_to_dict(session) for session in sessions])

    @app.custom_route("/api/entries", methods=["POST"])
    async def record_entry(request: Request) -> Response:
        try:
            data = await _json_body(request)
            entry = _service().record_summary(
                summary=str(data.get("summary", "")),
                project_id=_optional_str(data.get("project_id") or data.get("project")),
                cwd=_optional_str(data.get("cwd")),
                codex_session_id=_codex_session_id(data),
                title=_optional_str(data.get("title")),
                device_id=_optional_str(data.get("device_id")),
                kind=_optional_str(data.get("kind")) or "summary",
            )
            return JSONResponse(entry_to_dict(entry))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/entries", methods=["GET"])
    async def list_entries(request: Request) -> Response:
        project = request.query_params.get("project") or request.query_params.get("project_id")
        group = request.query_params.get("group") or request.query_params.get("group_id")
        session_id = request.query_params.get("session_id")
        try:
            if group:
                entries = _service().list_group_entries(group)
            elif project:
                entries = _service().list_project_entries(project)
            elif session_id:
                entries = _service().list_entries(session_id)
            else:
                return JSONResponse({"error": "project, group, or session_id query parameter is required"}, status_code=400)
            return JSONResponse([entry_to_dict(entry) for entry in entries])
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/hooks/codex", methods=["POST"])
    async def ingest_codex_hook(request: Request) -> Response:
        try:
            data = await _json_body(request)
            event = _optional_str(data.get("event"))
            payload = data.get("payload")
            if not event:
                raise ValueError("event is required")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            return JSONResponse(_service().ingest_codex_hook(event, payload))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/sync/export", methods=["GET"])
    async def sync_export(request: Request) -> Response:
        project = request.query_params.get("project")
        if not project:
            return JSONResponse({"error": "project query parameter is required"}, status_code=400)
        return JSONResponse(export_project(_service().store, project))

    @app.custom_route("/api/sync/import", methods=["POST"])
    async def sync_import(request: Request) -> Response:
        try:
            payload = await _json_body(request)
            return JSONResponse(import_sessions(_service().store, payload))
        except (ValueError, KeyError) as exc:
            return _error_response(exc)


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _codex_session_id(data: dict[str, Any]) -> str | None:
    return _optional_str(data.get("codex_session_id") or data.get("codexSessionId"))


def _tags(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        return tags or None
    if isinstance(value, list):
        return [str(tag) for tag in value]
    raise ValueError("tags must be a list or comma-separated string")


def _turns(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("turns must be a list")
    return [_turn_input(turn) for turn in value]


def _turn_input(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("turns must contain objects")
    return {
        "prompt": str(value.get("prompt", "")),
        "output": str(value.get("output", "")),
    }


def _error_response(exc: Exception) -> JSONResponse:
    status_code = 404 if isinstance(exc, SessionNotFoundError) else 400
    return JSONResponse({"error": str(exc)}, status_code=status_code)
