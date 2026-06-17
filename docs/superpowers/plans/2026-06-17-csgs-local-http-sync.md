# CSGS Local HTTP and Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local HTTP MCP daemon backed by SQLite, with hook-friendly JSON endpoints and project-scoped sync export/import helpers.

**Architecture:** FastMCP remains the MCP implementation and runs with `streamable-http` on `/mcp`. The same FastMCP app registers custom Starlette JSON routes under `/api/*`. SQLite stays local and receives additive migration columns for sync metadata.

**Tech Stack:** Python 3.11+, SQLite via `sqlite3`, MCP Python SDK/FastMCP, Starlette test client, pytest, argparse.

## Global Constraints

- Default to local-first SQLite; normal run logging must not require a central service.
- Default HTTP host is `127.0.0.1`; do not implement public auth in this MVP.
- `parent_id` remains an origin reference only, not an execution dependency.
- Sync MVP is append-only: import missing IDs, skip existing IDs, do not overwrite.
- Preserve existing CLI, stdio MCP, and tests.

---

### Task 1: Sync Metadata Migration

**Files:**
- Modify: `csgs/models.py`
- Modify: `csgs/store.py`
- Modify: `tests/test_store.py`

**Interfaces:**
- Produces: `Run.device_id: str | None`, `Run.updated_at: str | None`, `Run.sync_state: str | None`.
- Produces: `RunStore.list_project_runs(project: str) -> list[Run]`.

- [ ] **Step 1: Write failing migration test**

```python
def test_store_adds_sync_metadata_columns(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()

    run = Run(
        id="A_001",
        parent_id=None,
        project="demo",
        prompt="Root",
        output="Output",
        summary="Summary.",
        tags=["idea"],
        device_id="local-device",
        sync_state="local",
    )

    saved = store.create_run(run)

    assert saved.device_id == "local-device"
    assert saved.sync_state == "local"
    assert saved.updated_at is not None
    assert [item.id for item in store.list_project_runs("demo")] == ["A_001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_store.py::test_store_adds_sync_metadata_columns -v`

Expected: FAIL because `Run` and `RunStore` do not support sync metadata.

- [ ] **Step 3: Implement additive migration**

Add optional dataclass fields, migrate missing columns with `PRAGMA table_info`, persist metadata, and implement `list_project_runs`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_store.py::test_store_adds_sync_metadata_columns -v`

Expected: PASS.

---

### Task 2: Project Sync Export/Import

**Files:**
- Create: `csgs/sync.py`
- Modify: `csgs/store.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `RunStore.list_project_runs`, `RunStore.get_run`, `RunStore.create_run`.
- Produces: `export_project(store: RunStore, project: str) -> dict[str, object]`.
- Produces: `import_runs(store: RunStore, payload: dict[str, object]) -> dict[str, int]`.

- [ ] **Step 1: Write failing sync tests**

```python
from csgs.models import Run
from csgs.store import RunStore
from csgs.sync import export_project, import_runs


def test_export_project_only_includes_matching_project(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()
    store.create_run(Run("A_001", None, "alpha", "Prompt", "Output", "Summary.", ["idea"]))
    store.create_run(Run("B_001", None, "beta", "Prompt", "Output", "Summary.", ["idea"]))

    payload = export_project(store, "alpha")

    assert payload["project"] == "alpha"
    assert [run["id"] for run in payload["runs"]] == ["A_001"]


def test_import_runs_skips_existing_ids(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()
    store.create_run(Run("A_001", None, "alpha", "Prompt", "Output", "Summary.", ["idea"]))

    result = import_runs(store, {
        "project": "alpha",
        "runs": [
            {"id": "A_001", "parent_id": None, "project": "alpha", "prompt": "Old", "output": "Old", "summary": "Old.", "tags": []},
            {"id": "A_002", "parent_id": "A_001", "project": "alpha", "prompt": "New", "output": "New", "summary": "New.", "tags": ["sync"]},
        ],
    })

    assert result == {"imported": 1, "skipped": 1}
    assert store.get_run("A_002").parent_id == "A_001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sync.py -v`

Expected: FAIL because `csgs.sync` does not exist.

- [ ] **Step 3: Implement sync helpers**

Serialize and deserialize `Run` values to dictionaries. Import missing runs only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sync.py -v`

Expected: PASS.

---

### Task 3: Hook-Friendly JSON API

**Files:**
- Create: `csgs/http_api.py`
- Modify: `csgs/mcp_server.py`
- Test: `tests/test_http_api.py`

**Interfaces:**
- Consumes: `SessionGraphService`, `export_project`, `import_runs`.
- Produces: `register_api_routes(app) -> None` where `app` is a FastMCP instance.

- [ ] **Step 1: Write failing HTTP API test**

```python
from starlette.testclient import TestClient

from csgs.mcp_server import create_mcp_app


def test_http_api_logs_and_exports_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    created = client.post("/api/runs", json={
        "id": "A_001",
        "project": "alpha",
        "prompt": "Root",
        "output": "Root output",
        "tags": ["idea"],
    })
    assert created.status_code == 200
    assert created.json()["summary"] == "Purpose: Root. Result: Root output."

    fetched = client.get("/api/runs/A_001")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == "A_001"

    exported = client.get("/api/sync/export", params={"project": "alpha"})
    assert exported.status_code == 200
    assert [run["id"] for run in exported.json()["runs"]] == ["A_001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_api.py::test_http_api_logs_and_exports_runs -v`

Expected: FAIL because API routes are not registered.

- [ ] **Step 3: Implement API routes**

Add Starlette JSON handlers for health, log, get, fork, trace, search, export, and import. Return clear `404` for missing runs and `400` for malformed JSON.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_http_api.py::test_http_api_logs_and_exports_runs -v`

Expected: PASS.

---

### Task 4: Daemon CLI and Documentation

**Files:**
- Modify: `csgs/mcp_server.py`
- Modify: `csgs/cli.py`
- Modify: `README.md`
- Test: `tests/test_mcp_server.py`
- Test: full suite

**Interfaces:**
- Produces: `python -m csgs.mcp_server --transport streamable-http --host 127.0.0.1 --port 8765`.
- Produces: `python -m csgs.cli serve --host 127.0.0.1 --port 8765`.

- [ ] **Step 1: Write failing daemon argument test**

```python
from csgs.mcp_server import create_mcp_app


def test_create_mcp_app_uses_http_settings(monkeypatch):
    monkeypatch.setenv("CSGS_HOST", "127.0.0.1")
    monkeypatch.setenv("CSGS_PORT", "8765")

    app = create_mcp_app()

    assert app.settings.host == "127.0.0.1"
    assert app.settings.port == 8765
    assert app.settings.streamable_http_path == "/mcp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_server.py::test_create_mcp_app_uses_http_settings -v`

Expected: FAIL because env HTTP settings are not wired.

- [ ] **Step 3: Implement daemon args and docs**

Add argparse to `csgs.mcp_server.main`, support stdio and streamable-http, expose CLI `serve`, and update README with local HTTP MCP and hook API examples.

- [ ] **Step 4: Run full verification**

Run: `python -m pytest -v`

Expected: all tests PASS.
