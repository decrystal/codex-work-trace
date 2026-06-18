from csgs.service import SessionGraphService
from csgs.store import CSGSStore
from csgs.sync import export_project, import_sessions
from csgs.config import write_config
from csgs.remote import get_json


def test_export_project_includes_only_sessions_and_turns(tmp_path):
    store = CSGSStore(tmp_path / "csgs.sqlite3")
    service = SessionGraphService(store)
    service.log_session(
        project="alpha",
        title="Alpha session",
        codex_session_id="codex-alpha",
        turns=[{"prompt": "Prompt", "output": "Output"}],
        session_id="S_001",
    )
    service.log_session(
        project="beta",
        title="Beta session",
        turns=[{"prompt": "Prompt", "output": "Output"}],
        session_id="S_002",
    )

    payload = export_project(store, "alpha")

    assert payload["project"] == "alpha"
    assert "runs" not in payload
    assert [session["id"] for session in payload["sessions"]] == ["S_001"]
    assert payload["sessions"][0]["codex_session_id"] == "codex-alpha"
    assert [turn["session_id"] for turn in payload["turns"]] == ["S_001"]
    assert payload["turns"][0]["codex_session_id"] == "codex-alpha"


def test_remote_client_uses_configured_token(tmp_path, monkeypatch):
    csgs_home = tmp_path / "csgs-home"
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))
    monkeypatch.delenv("CSGS_TOKEN", raising=False)
    write_config(mode="remote", endpoint="https://csgs.example.com", token="sync-secret")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.headers.get("Authorization")
        return FakeResponse()

    monkeypatch.setattr("csgs.remote.urlopen", fake_urlopen)

    get_json("https://csgs.example.com", "/api/sync/export", {"project": "alpha"})

    assert captured["authorization"] == "Bearer sync-secret"


def test_import_sessions_imports_sessions_and_turns_append_only(tmp_path):
    store = CSGSStore(tmp_path / "csgs.sqlite3")
    service = SessionGraphService(store)
    service.log_session(
        project="alpha",
        title="Existing",
        turns=[{"prompt": "Old", "output": "Old"}],
        session_id="S_001",
    )

    result = import_sessions(
        store,
        {
            "project": "alpha",
            "sessions": [
                {
                    "id": "S_001",
                    "parent_id": None,
                    "project": "alpha",
                    "title": "Existing rewritten",
                    "summary": "Should not overwrite.",
                    "tags": [],
                    "summary_turn_index": 1,
                },
                {
                    "id": "S_002",
                    "parent_id": "S_001",
                    "project": "alpha",
                    "codex_session_id": "codex-imported",
                    "title": "Imported",
                    "summary": "Imported summary.",
                    "tags": ["sync"],
                    "summary_turn_index": 1,
                },
            ],
            "turns": [
                {
                    "id": "T_002",
                    "session_id": "S_002",
                    "codex_session_id": "codex-imported",
                    "turn_index": 1,
                    "prompt": "Imported",
                    "output": "Imported",
                    "summary": "Imported turn.",
                }
            ],
        },
    )

    assert result == {"imported": 2, "skipped": 1}
    assert store.get_session("S_001").title == "Existing"
    assert store.get_session("S_002").parent_id == "S_001"
    assert store.get_session("S_002").codex_session_id == "codex-imported"
    assert store.list_turns("S_002")[0].summary == "Imported turn."
    assert store.list_turns("S_002")[0].codex_session_id == "codex-imported"
