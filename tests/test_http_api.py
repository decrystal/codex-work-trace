from starlette.testclient import TestClient

from csgs.mcp_server import create_mcp_app


def test_http_auth_is_disabled_when_token_is_not_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    monkeypatch.delenv("CSGS_TOKEN", raising=False)
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    response = client.get("/api/search")

    assert response.status_code == 200


def test_http_auth_protects_api_ui_and_mcp_when_token_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    monkeypatch.setenv("CSGS_TOKEN", "secret-token")
    app = create_mcp_app().streamable_http_app()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/search").status_code == 401
        assert client.get("/ui").status_code == 401
        assert client.get("/mcp").status_code == 401

        api = client.get("/api/search", headers={"Authorization": "Bearer secret-token"})
        ui = client.get("/ui?token=secret-token")
        mcp = client.get("/mcp", headers={"x-csgs-token": "secret-token"})

        assert api.status_code == 200
        assert ui.status_code == 200
        assert "CSGS Explorer" in ui.text
        assert mcp.status_code != 401


def test_ui_page_is_available_without_token_in_local_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    monkeypatch.delenv("CSGS_TOKEN", raising=False)
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    response = client.get("/ui")

    assert response.status_code == 200
    assert "CSGS Explorer" in response.text
    assert "/api/entries" in response.text


def test_http_api_has_no_run_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    assert client.post("/api/runs", json={}).status_code == 404
    assert client.get("/api/runs/A_001").status_code == 404


def test_http_api_logs_session_and_appends_turn_incrementally(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    created = client.post(
        "/api/sessions",
        json={
            "id": "S_001",
            "project": "alpha",
            "codexSessionId": "codex-session-123",
            "title": "CSGS session model",
            "tags": ["session"],
            "turns": [
                {"prompt": "Design session model", "output": "Added sessions and turns"},
                {"prompt": "Make append cheap", "output": "Use existing summary plus new turn summary"},
            ],
        },
    )
    assert created.status_code == 200
    assert created.json()["codex_session_id"] == "codex-session-123"
    assert created.json()["summary_turn_index"] == 2

    appended = client.post(
        "/api/sessions/S_001/turns",
        json={"prompt": "Expose HTTP API", "output": "Added session endpoints"},
    )
    assert appended.status_code == 200
    assert appended.json()["codex_session_id"] == "codex-session-123"
    assert appended.json()["turn_index"] == 3

    fetched = client.get("/api/sessions/S_001")
    assert fetched.status_code == 200
    assert fetched.json()["codex_session_id"] == "codex-session-123"
    assert fetched.json()["summary_turn_index"] == 3
    assert "Expose HTTP API" in fetched.json()["summary"]

    turns = client.get("/api/sessions/S_001/turns")
    assert [turn["turn_index"] for turn in turns.json()] == [1, 2, 3]
    assert [turn["codex_session_id"] for turn in turns.json()] == [
        "codex-session-123",
        "codex-session-123",
        "codex-session-123",
    ]


def test_http_append_can_backfill_codex_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    client.post(
        "/api/sessions",
        json={"id": "S_001", "project": "alpha", "turns": [{"prompt": "Root", "output": "Root output"}]},
    )
    appended = client.post(
        "/api/sessions/S_001/turns",
        json={"prompt": "Append", "output": "Output", "codexSessionId": "codex-http-append"},
    )
    fetched = client.get("/api/sessions/S_001")

    assert appended.status_code == 200
    assert appended.json()["codex_session_id"] == "codex-http-append"
    assert fetched.json()["codex_session_id"] == "codex-http-append"


def test_http_api_records_and_lists_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    recorded = client.post(
        "/api/entries",
        json={
            "summary": "HTTP entry.",
            "project_id": "github:decrytal-ade/codex-work-trace",
            "codex_session_id": "codex-http-entry",
        },
    )
    assert recorded.status_code == 200
    assert recorded.json()["summary"] == "HTTP entry."

    listed = client.get("/api/entries", params={"project": "github:decrytal-ade/codex-work-trace"})
    assert listed.status_code == 200
    assert [entry["summary"] for entry in listed.json()] == ["HTTP entry."]


def test_http_api_ingests_codex_hook_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    prompt = client.post(
        "/api/hooks/codex",
        json={
            "event": "UserPromptSubmit",
            "payload": {
                "session_id": "codex-http-hook",
                "turn_id": "turn-http-hook",
                "cwd": str(tmp_path / "demo"),
                "prompt": "Record through remote hook",
            },
        },
    )
    assert prompt.status_code == 200
    assert prompt.json()["status"] == "pending"

    stop = client.post(
        "/api/hooks/codex",
        json={
            "event": "Stop",
            "payload": {
                "session_id": "codex-http-hook",
                "turn_id": "turn-http-hook",
                "cwd": str(tmp_path / "demo"),
                "last_assistant_message": "Recorded through remote hook.",
            },
        },
    )
    assert stop.status_code == 200
    assert stop.json()["status"] == "recorded"

    session = client.get("/api/sessions/S_codex_codex_http_hook")
    assert session.status_code == 200
    assert session.json()["codex_session_id"] == "codex-http-hook"

    turns = client.get("/api/sessions/S_codex_codex_http_hook/turns")
    assert turns.json()[0]["codex_turn_id"] == "turn-http-hook"


def test_http_api_forks_traces_searches_and_syncs_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    app = create_mcp_app().streamable_http_app()
    client = TestClient(app)

    client.post(
        "/api/sessions",
        json={
            "id": "S_001",
            "project": "alpha",
            "codex_session_id": "codex-root",
            "turns": [{"prompt": "Root", "output": "Root output"}],
        },
    )

    forked = client.post(
        "/api/sessions/S_001/fork",
        json={
            "id": "S_002",
            "codexSessionId": "codex-child",
            "turns": [{"prompt": "Branch", "output": "Branch output"}],
        },
    )
    assert forked.status_code == 200
    assert forked.json()["parent_id"] == "S_001"
    assert forked.json()["codex_session_id"] == "codex-child"

    trace = client.get("/api/sessions/S_002/trace")
    assert trace.status_code == 200
    assert "S_001" in trace.text
    assert "S_002" in trace.text

    search = client.get("/api/search", params={"project": "alpha", "text": "Branch"})
    assert [session["id"] for session in search.json()] == ["S_002"]

    exported = client.get("/api/sync/export", params={"project": "alpha"})
    assert exported.status_code == 200
    assert "runs" not in exported.json()
    assert [session["id"] for session in exported.json()["sessions"]] == ["S_001", "S_002"]

    imported = client.post("/api/sync/import", json=exported.json())
    assert imported.status_code == 200
    assert imported.json()["skipped"] == 4
