from starlette.testclient import TestClient

from csgs.mcp_server import create_mcp_app


def test_http_api_logs_and_exports_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    created = client.post(
        "/api/runs",
        json={
            "id": "A_001",
            "project": "alpha",
            "prompt": "Root",
            "output": "Root output",
            "tags": ["idea"],
        },
    )
    assert created.status_code == 200
    assert created.json()["summary"] == "Purpose: Root. Result: Root output."

    fetched = client.get("/api/runs/A_001")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == "A_001"

    exported = client.get("/api/sync/export", params={"project": "alpha"})
    assert exported.status_code == 200
    assert [run["id"] for run in exported.json()["runs"]] == ["A_001"]


def test_http_api_forks_traces_and_imports_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    client.post("/api/runs", json={"id": "A_001", "project": "alpha", "prompt": "Root", "output": "Root output"})

    forked = client.post(
        "/api/runs/A_001/fork",
        json={"id": "B_002", "prompt": "Branch", "output": "Branch output"},
    )
    assert forked.status_code == 200
    assert forked.json()["parent_id"] == "A_001"

    trace = client.get("/api/runs/B_002/trace")
    assert trace.status_code == 200
    assert "A_001" in trace.text
    assert "B_002" in trace.text

    imported = client.post(
        "/api/sync/import",
        json={
            "project": "alpha",
            "runs": [
                {
                    "id": "A_001",
                    "parent_id": None,
                    "project": "alpha",
                    "prompt": "Existing",
                    "output": "Existing",
                    "summary": "Existing.",
                    "tags": [],
                },
                {
                    "id": "C_003",
                    "parent_id": "A_001",
                    "project": "alpha",
                    "prompt": "Imported",
                    "output": "Imported",
                    "summary": "Imported.",
                    "tags": ["sync"],
                },
            ],
        },
    )
    assert imported.status_code == 200
    assert imported.json() == {"imported": 1, "skipped": 1}
