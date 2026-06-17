from __future__ import annotations

from json import JSONDecodeError
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from csgs.errors import CSGSError
from csgs.mcp_server import _db_path, _service
from csgs.sync import export_project, import_runs, run_to_dict


def register_api_routes(app: Any) -> None:
    @app.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok", "db": str(_db_path())})

    @app.custom_route("/api/runs", methods=["POST"])
    async def create_run(request: Request) -> Response:
        try:
            data = await _json_body(request)
            run = _service().log_run(
                prompt=str(data.get("prompt", "")),
                output=str(data.get("output", "")),
                parent_id=_optional_str(data.get("parent_id")),
                project=_optional_str(data.get("project")),
                tags=_tags(data.get("tags")),
                run_id=_optional_str(data.get("id") or data.get("run_id")),
            )
            return JSONResponse(run_to_dict(run))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/runs/{run_id}", methods=["GET"])
    async def get_run(request: Request) -> Response:
        try:
            return JSONResponse(run_to_dict(_service().get_run(request.path_params["run_id"])))
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/runs/{run_id}/fork", methods=["POST"])
    async def fork_run(request: Request) -> Response:
        try:
            data = await _json_body(request)
            run = _service().fork_run(
                source_id=request.path_params["run_id"],
                prompt=_optional_str(data.get("prompt")),
                output=_optional_str(data.get("output")),
                project=_optional_str(data.get("project")),
                tags=_tags(data.get("tags")),
                run_id=_optional_str(data.get("id") or data.get("run_id")),
            )
            return JSONResponse(run_to_dict(run))
        except (CSGSError, ValueError, KeyError) as exc:
            return _error_response(exc)

    @app.custom_route("/api/runs/{run_id}/trace", methods=["GET"])
    async def trace_run(request: Request) -> Response:
        try:
            return PlainTextResponse(_service().trace_run(request.path_params["run_id"]))
        except CSGSError as exc:
            return _error_response(exc)

    @app.custom_route("/api/search", methods=["GET"])
    async def search_runs(request: Request) -> Response:
        tags = _tags(request.query_params.get("tags"))
        runs = _service().search_runs(
            text=request.query_params.get("text"),
            tags=tags,
            project=request.query_params.get("project"),
        )
        return JSONResponse([run_to_dict(run) for run in runs])

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
            return JSONResponse(import_runs(_service().store, payload))
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


def _tags(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        return tags or None
    if isinstance(value, list):
        return [str(tag) for tag in value]
    raise ValueError("tags must be a list or comma-separated string")


def _error_response(exc: Exception) -> JSONResponse:
    status_code = 404 if exc.__class__.__name__ == "RunNotFoundError" else 400
    return JSONResponse({"error": str(exc)}, status_code=status_code)
