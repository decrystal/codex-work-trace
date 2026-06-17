import asyncio

from csgs import mcp_server


def test_mcp_log_and_get_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    created = asyncio.run(mcp_server.log_run(prompt="Root", output="Root output", run_id="A_001"))
    fetched = asyncio.run(mcp_server.get_run("A_001"))

    assert created["id"] == "A_001"
    assert fetched["summary"] == created["summary"]


def test_create_mcp_app_uses_http_settings(monkeypatch):
    monkeypatch.setenv("CSGS_HOST", "127.0.0.1")
    monkeypatch.setenv("CSGS_PORT", "8765")

    app = mcp_server.create_mcp_app()

    assert app.settings.host == "127.0.0.1"
    assert app.settings.port == 8765
    assert app.settings.streamable_http_path == "/mcp"


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
    assert appended["turn_index"] == 2
    assert fetched["summary_turn_index"] == 2
