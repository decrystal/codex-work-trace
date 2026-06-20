import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from csgs import mcp_server
from csgs.service import SessionGraphService
from csgs.store import CSGSStore


def test_mcp_module_exposes_only_session_tools():
    assert not hasattr(mcp_server, "log_run")
    assert not hasattr(mcp_server, "get_run")
    assert not hasattr(mcp_server, "trace_run")
    assert not hasattr(mcp_server, "fork_run")
    assert hasattr(mcp_server, "log_session")
    assert hasattr(mcp_server, "append_turn")
    assert hasattr(mcp_server, "fork_session")
    assert hasattr(mcp_server, "record_summary")
    assert hasattr(mcp_server, "get_runtime_context")
    assert hasattr(mcp_server, "record_current_session_summary")
    assert hasattr(mcp_server, "list_project_entries")


def test_mcp_instructions_prioritize_current_summary_tool():
    assert "record_current_session_summary" in mcp_server.INSTRUCTIONS
    assert "用 CSGS 总结" in mcp_server.INSTRUCTIONS
    assert "get_runtime_context" in mcp_server.INSTRUCTIONS


def test_create_mcp_app_uses_http_settings(monkeypatch):
    monkeypatch.setenv("CSGS_HOST", "127.0.0.1")
    monkeypatch.setenv("CSGS_PORT", "8765")

    app = mcp_server.create_mcp_app()

    assert app.settings.host == "127.0.0.1"
    assert app.settings.port == 8765
    assert app.settings.streamable_http_path == "/mcp"


def test_create_mcp_app_initializes_schema(tmp_path, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")

    monkeypatch.setenv("CSGS_DB", str(db))

    mcp_server.create_mcp_app()

    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert "sessions" in tables
    assert "turns" in tables
    assert "runs" not in tables


def test_mcp_server_main_handles_keyboard_interrupt(monkeypatch):
    class InterruptingApp:
        def run(self, transport):
            raise KeyboardInterrupt

    monkeypatch.setattr(mcp_server, "create_mcp_app", lambda host=None, port=None: InterruptingApp())

    result = mcp_server.main(["--transport", "streamable-http"])

    assert result == 130


def test_mcp_session_tools_log_and_append_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    created = asyncio.run(
        mcp_server.log_session(
            project="alpha",
            codex_session_id="codex-session-123",
            turns=[{"prompt": "Design session model", "output": "Added session and turn tables"}],
            session_id="S_001",
            title="Session model",
        )
    )
    appended = asyncio.run(
        mcp_server.append_turn(
            session_id="S_001",
            prompt="Append cheaply",
            output="Use old summary plus new turn summary",
        )
    )
    fetched = asyncio.run(mcp_server.get_session("S_001"))

    assert created["id"] == "S_001"
    assert created["codex_session_id"] == "codex-session-123"
    assert appended["turn_index"] == 2
    assert appended["codex_session_id"] == "codex-session-123"
    assert fetched["summary_turn_index"] == 2


def test_mcp_log_session_allows_missing_codex_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    created = asyncio.run(
        mcp_server.log_session(
            project="alpha",
            turns=[{"prompt": "Root", "output": "Root output"}],
            session_id="S_001",
        )
    )

    assert created["id"] == "S_001"
    assert created["codex_session_id"] is None


def test_mcp_fork_session_allows_missing_codex_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    asyncio.run(
        mcp_server.log_session(
            project="alpha",
            codex_session_id="codex-root",
            turns=[{"prompt": "Root", "output": "Root output"}],
            session_id="S_001",
        )
    )

    forked = asyncio.run(
        mcp_server.fork_session(
            id="S_001",
            turns=[{"prompt": "Branch", "output": "Branch output"}],
            session_id="S_002",
        )
    )

    assert forked["id"] == "S_002"
    assert forked["parent_id"] == "S_001"
    assert forked["codex_session_id"] is None


def test_mcp_append_can_backfill_codex_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3")).log_session(
        project="alpha",
        turns=[{"prompt": "Root", "output": "Root output"}],
        session_id="S_001",
    )
    appended = asyncio.run(
        mcp_server.append_turn(
            session_id="S_001",
            prompt="Append",
            output="Output",
            codex_session_id="codex-mcp-append",
        )
    )
    fetched = asyncio.run(mcp_server.get_session("S_001"))

    assert appended["codex_session_id"] == "codex-mcp-append"
    assert fetched["codex_session_id"] == "codex-mcp-append"


def test_mcp_records_and_lists_summary_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    recorded = asyncio.run(
        mcp_server.record_summary(
            summary="MCP entry.",
            project_id="github:decrytal-ade/codex-work-trace",
            codex_session_id="codex-mcp-entry",
        )
    )
    entries = asyncio.run(mcp_server.list_project_entries("github:decrytal-ade/codex-work-trace"))

    assert recorded["project_id"] == "github:decrytal-ade/codex-work-trace"
    assert recorded["summary"] == "MCP entry."
    assert [entry["summary"] for entry in entries] == ["MCP entry."]


@dataclass
class _FakeRoot:
    uri: str
    name: str | None = None


class _FakeSession:
    def __init__(self, roots):
        self._roots = roots

    async def list_roots(self):
        return type("RootsResult", (), {"roots": self._roots})()


class _FakeRequestContext:
    def __init__(self, *, session, meta=None, request_id="req-1"):
        self.session = session
        self.meta = meta
        self.request_id = request_id


class _FakeContext:
    def __init__(self, *, roots, meta=None):
        self.request_context = _FakeRequestContext(session=_FakeSession(roots), meta=meta)
        self.request_id = "req-1"
        self.client_id = getattr(meta, "client_id", None) if meta is not None else None


class _TrackingSession:
    def __init__(self):
        self.list_roots_called = False

    async def list_roots(self):
        self.list_roots_called = True
        return type("RootsResult", (), {"roots": []})()


class _TrackingContext:
    def __init__(self, *, session, meta=None):
        self.request_context = _FakeRequestContext(session=session, meta=meta)
        self.request_id = "req-track"
        self.client_id = None


class _SlowSession:
    async def list_roots(self):
        await asyncio.sleep(10)
        return type("RootsResult", (), {"roots": []})()


def test_get_runtime_context_uses_roots_meta_and_project_derivation(tmp_path, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("CSGS_DB", str(db))
    meta = type("Meta", (), {"client_id": "codex-client", "codex_session_id": "codex-meta-session"})()
    ctx = _FakeContext(roots=[_FakeRoot(uri=project.as_uri(), name="project")], meta=meta)

    runtime = asyncio.run(mcp_server.get_runtime_context(ctx))

    assert runtime["db_path"] == str(db)
    assert runtime["cwd"] == str(project)
    assert runtime["project_id"] == f"path:{project}"
    assert runtime["codex_session_id"] == "codex-meta-session"
    assert runtime["mcp_request"]["client_id"] == "codex-client"
    assert runtime["roots"] == [{"uri": project.as_uri(), "name": "project"}]


def test_get_runtime_context_times_out_slow_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    monkeypatch.setenv("CSGS_ROOTS_TIMEOUT", "0.01")
    ctx = _TrackingContext(session=_SlowSession())

    runtime = asyncio.run(asyncio.wait_for(mcp_server.get_runtime_context(ctx), timeout=0.2))

    assert runtime["roots"] == []
    assert runtime["cwd"] is None
    assert runtime["project_id"] is None


def test_record_current_session_summary_uses_context_fallbacks(tmp_path, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("CSGS_DB", str(db))
    meta = type("Meta", (), {"codex_thread_id": "codex-context-thread"})()
    ctx = _FakeContext(roots=[_FakeRoot(uri=project.as_uri(), name="project")], meta=meta)

    recorded = asyncio.run(
        mcp_server.record_current_session_summary(
            summary="Recorded through context-aware MCP.",
            ctx=ctx,
        )
    )

    assert recorded["project_id"] == f"path:{project}"
    assert recorded["codex_session_id"] == "codex-context-thread"
    assert recorded["db_path"] == str(db)
    assert recorded["summary"] == "Recorded through context-aware MCP."

    store = CSGSStore(db)
    session = store.get_session(recorded["session_id"])
    assert session is not None
    assert session.codex_session_id == "codex-context-thread"


def test_record_current_session_summary_with_explicit_windows_cwd_skips_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))
    session = _TrackingSession()
    ctx = _TrackingContext(session=session)

    recorded = asyncio.run(
        mcp_server.record_current_session_summary(
            summary="Recorded from Windows project.",
            cwd=r"C:\code\media-crawl",
            codex_session_id="codex-windows",
            ctx=ctx,
        )
    )

    assert session.list_roots_called is False
    assert recorded["project_id"] == "path:C:/code/media-crawl"
    assert recorded["runtime_context"]["cwd"] == r"C:\code\media-crawl"


def test_mcp_fork_session(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    asyncio.run(
        mcp_server.log_session(
            project="alpha",
            codex_session_id="codex-root",
            turns=[{"prompt": "Root", "output": "Root output"}],
            session_id="S_001",
        )
    )
    forked = asyncio.run(
        mcp_server.fork_session(
            id="S_001",
            turns=[{"prompt": "Branch", "output": "Branch output"}],
            codex_session_id="codex-child",
            session_id="S_002",
        )
    )

    assert forked["id"] == "S_002"
    assert forked["parent_id"] == "S_001"
    assert forked["codex_session_id"] == "codex-child"
