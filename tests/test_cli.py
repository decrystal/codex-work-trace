import io
import json

from csgs.cli import main
from csgs.config import write_config
from csgs.store import CSGSStore


def test_cli_session_fork_and_trace(tmp_path, capsys, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread-cli")

    assert main(["--db", str(db), "session-log", "--id", "S_001", "--turn", "Root|||Root output"]) == 0
    assert (
        main(
            [
                "--db",
                str(db),
                "session-fork",
                "S_001",
                "--id",
                "S_002",
                "--codex-session-id",
                "codex-child",
                "--turn",
                "Child|||Child output",
            ]
        )
        == 0
    )
    assert main(["--db", str(db), "session-trace", "S_002"]) == 0

    captured = capsys.readouterr()
    assert "S_001" in captured.out
    assert "S_002" in captured.out
    assert CSGSStore(db).get_session("S_001").codex_session_id == "codex-thread-cli"


def test_cli_serve_delegates_to_mcp_server(tmp_path, monkeypatch):
    called = {}

    def fake_main(argv):
        called["argv"] = argv
        return 0

    monkeypatch.setattr("csgs.mcp_server.main", fake_main)

    result = main(
        [
            "--db",
            str(tmp_path / "csgs.sqlite3"),
            "serve",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]
    )

    assert result == 0
    assert called["argv"] == [
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
        "--db",
        str(tmp_path / "csgs.sqlite3"),
    ]


def test_cli_mcp_server_delegates_to_stdio_mcp_server(tmp_path, monkeypatch):
    called = {}

    def fake_main(argv):
        called["argv"] = argv
        return 0

    monkeypatch.setattr("csgs.mcp_server.main", fake_main)

    result = main(["--db", str(tmp_path / "csgs.sqlite3"), "mcp-server"])

    assert result == 0
    assert called["argv"] == [
        "--transport",
        "stdio",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
        "--db",
        str(tmp_path / "csgs.sqlite3"),
    ]


def test_cli_logs_session_and_appends_turn(tmp_path, capsys):
    db = tmp_path / "csgs.sqlite3"

    assert (
        main(
            [
                "--db",
                str(db),
                "session-log",
                "--id",
                "S_001",
                "--project",
                "alpha",
                "--title",
                "Session model",
                "--codex-session-id",
                "codex-session-123",
                "--turn",
                "Design sessions|||Added sessions and turns",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--db",
                str(db),
                "turn-append",
                "S_001",
                "--prompt",
                "Append cheaply",
                "--output",
                "Used summary plus new turn summary",
            ]
        )
        == 0
    )
    assert main(["--db", str(db), "session-get", "S_001"]) == 0

    captured = capsys.readouterr()
    assert '"id": "S_001"' in captured.out
    assert '"codex_session_id": "codex-session-123"' in captured.out
    assert '"summary_turn_index": 2' in captured.out


def test_cli_record_summary_uses_codex_thread_and_path_project(tmp_path, capsys, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    cwd = tmp_path / "plain-folder"
    cwd.mkdir()
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-record-cli")

    assert (
        main(
            [
                "--db",
                str(db),
                "record-summary",
                "--summary",
                "Recorded on demand.",
                "--cwd",
                str(cwd),
                "--title",
                "On demand",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert '"project_id": "path:' in captured.out
    assert '"codex_session_id": "codex-record-cli"' in captured.out
    assert '"summary": "Recorded on demand."' in captured.out


def test_cli_group_add_project_and_entries_query(tmp_path, capsys):
    db = tmp_path / "csgs.sqlite3"

    assert main(["--db", str(db), "group-add-project", "csgs", "github:decrytal-ade/codex-work-trace"]) == 0
    assert (
        main(
            [
                "--db",
                str(db),
                "record-summary",
                "--summary",
                "Grouped entry.",
                "--project",
                "github:decrytal-ade/codex-work-trace",
                "--codex-session-id",
                "codex-group-cli",
            ]
        )
        == 0
    )
    assert main(["--db", str(db), "entry-list", "--group", "csgs"]) == 0

    captured = capsys.readouterr()
    assert '"project_id": "github:decrytal-ade/codex-work-trace"' in captured.out
    assert '"summary": "Grouped entry."' in captured.out


def test_cli_record_summary_auto_syncs_when_remote_is_configured(tmp_path, monkeypatch, capsys):
    csgs_home = tmp_path / "csgs-home"
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))
    monkeypatch.delenv("CSGS_DB", raising=False)
    write_config(mode="remote", endpoint="https://csgs.example.com")
    calls = []

    def fake_sync(store, endpoint, project):
        calls.append((str(store.db_path), endpoint, project))
        return {"pushed": {"imported": 1, "skipped": 0}, "pulled": {"imported": 0, "skipped": 1}}

    monkeypatch.setattr("csgs.cli.sync_project_with_remote", fake_sync)

    assert (
        main(
            [
                "record-summary",
                "--summary",
                "Auto synced.",
                "--project",
                "github:decrytal-ade/codex-work-trace",
                "--codex-session-id",
                "codex-auto-sync",
            ]
        )
        == 0
    )

    assert calls == [
        (
            str(csgs_home / "csgs.sqlite3"),
            "https://csgs.example.com",
            "github:decrytal-ade/codex-work-trace",
        )
    ]
    assert '"sync": {' in capsys.readouterr().out


def test_cli_append_backfills_codex_thread_id(tmp_path, monkeypatch):
    db = tmp_path / "csgs.sqlite3"

    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    assert main(["--db", str(db), "session-log", "--id", "S_001", "--turn", "Root|||Root output"]) == 0
    assert CSGSStore(db).get_session("S_001").codex_session_id is None

    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread-append")
    assert (
        main(
            [
                "--db",
                str(db),
                "turn-append",
                "S_001",
                "--prompt",
                "Append",
                "--output",
                "Output",
            ]
        )
        == 0
    )

    store = CSGSStore(db)
    assert store.get_session("S_001").codex_session_id == "codex-thread-append"
    assert store.list_turns("S_001")[-1].codex_session_id == "codex-thread-append"


def test_cli_install_local_writes_csgs_config_and_mcp_server(tmp_path, capsys, monkeypatch):
    codex_home = tmp_path / "codex-home"
    csgs_home = tmp_path / "csgs-home"
    db = tmp_path / "csgs.sqlite3"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))

    assert main(["install", "--mode", "local", "--runtime", "dev-python", "--db", str(db)]) == 0

    csgs_config = (csgs_home / "config.toml").read_text()

    assert 'mode = "local"' in csgs_config
    assert f'db = "{db}"' in csgs_config
    codex_config = (codex_home / "config.toml").read_text()
    assert "[mcp_servers.csgs]" in codex_config
    assert 'args = ["-m", "csgs.mcp_server"]' in codex_config
    assert f'CSGS_DB = "{db}"' in codex_config
    assert not (codex_home / "hooks.json").exists()

    captured = capsys.readouterr()
    assert "CSGS local install complete" in captured.out
    assert "Codex MCP: configured" in captured.out
    assert "/hooks" not in captured.out


def test_cli_install_local_does_not_touch_existing_codex_hooks(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-home"
    csgs_home = tmp_path / "csgs-home"
    db = tmp_path / "csgs.sqlite3"
    csgs_bin = tmp_path / "bin" / "csgs"
    csgs_bin.parent.mkdir()
    csgs_bin.write_text("#!/bin/sh\n")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))
    old_hook_script = codex_home / "hooks" / "csgs_ingest.py"
    old_hook_script.parent.mkdir(parents=True)
    old_hook_script.write_text("old")

    assert (
        main(
            [
                "install",
                "--mode",
                "local",
                "--runtime",
                "binary",
                "--bin",
                str(csgs_bin),
                "--db",
                str(db),
            ]
        )
        == 0
    )

    codex_config = (codex_home / "config.toml").read_text()
    assert "[mcp_servers.csgs]" in codex_config
    assert old_hook_script.read_text() == "old"
    assert f'db = "{db}"' in (csgs_home / "config.toml").read_text()


def test_cli_install_remote_writes_csgs_config_and_remote_mcp(tmp_path, monkeypatch, capsys):
    codex_home = tmp_path / "codex-home"
    csgs_home = tmp_path / "csgs-home"
    csgs_bin = tmp_path / "bin" / "csgs"
    csgs_bin.parent.mkdir()
    csgs_bin.write_text("#!/bin/sh\n")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))

    assert (
        main(
            [
                "install",
                "--mode",
                "remote",
                "--endpoint",
                "https://csgs.example.com",
                "--runtime",
                "binary",
                "--bin",
                str(csgs_bin),
            ]
        )
        == 0
    )

    csgs_config = (csgs_home / "config.toml").read_text()
    expected_db = csgs_home / "csgs.sqlite3"

    codex_config = (codex_home / "config.toml").read_text()
    assert "[mcp_servers.csgs]" in codex_config
    assert 'url = "https://csgs.example.com/mcp"' in codex_config
    assert not (codex_home / "hooks.json").exists()
    assert 'mode = "remote"' in csgs_config
    assert f'db = "{expected_db}"' in csgs_config
    assert 'endpoint = "https://csgs.example.com"' in csgs_config

    captured = capsys.readouterr()
    assert "CSGS remote install complete" in captured.out
    assert "MCP endpoint: https://csgs.example.com/mcp" in captured.out


def test_cli_install_remote_can_write_token_header(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-home"
    csgs_home = tmp_path / "csgs-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))

    assert (
        main(
            [
                "install",
                "--mode",
                "remote",
                "--endpoint",
                "https://csgs.example.com",
                "--token",
                "remote-secret",
            ]
        )
        == 0
    )

    csgs_config = (csgs_home / "config.toml").read_text()
    codex_config = (codex_home / "config.toml").read_text()
    assert 'token = "remote-secret"' in csgs_config
    assert "[mcp_servers.csgs.headers]" in codex_config
    assert 'Authorization = "Bearer remote-secret"' in codex_config


def test_cli_hook_ingest_records_codex_turn(tmp_path, monkeypatch):
    db = tmp_path / "csgs.sqlite3"
    cwd = tmp_path / "demo-project"
    cwd.mkdir()

    prompt_payload = {
        "session_id": "codex-session-1",
        "turn_id": "codex-turn-1",
        "cwd": str(cwd),
        "transcript_path": str(tmp_path / "session.jsonl"),
        "prompt": "Build local hook ingestion",
        "model": "gpt-test",
    }
    stop_payload = {
        "session_id": "codex-session-1",
        "turn_id": "codex-turn-1",
        "cwd": str(cwd),
        "transcript_path": str(tmp_path / "session.jsonl"),
        "last_assistant_message": "Implemented local hook ingestion.",
        "model": "gpt-test",
    }

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(prompt_payload)))
    assert main(["--db", str(db), "hook-ingest", "--event", "UserPromptSubmit"]) == 0

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stop_payload)))
    assert main(["--db", str(db), "hook-ingest", "--event", "Stop"]) == 0

    store = CSGSStore(db)
    session = store.get_session_by_codex_session_id("codex-session-1")
    assert session is not None
    assert session.project == f"path:{cwd}"

    turns = store.list_turns(session.id)
    assert len(turns) == 1
    assert turns[0].codex_session_id == "codex-session-1"
    assert turns[0].codex_turn_id == "codex-turn-1"
    assert turns[0].prompt == "Build local hook ingestion"
    assert turns[0].output == "Implemented local hook ingestion."

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stop_payload)))
    assert main(["--db", str(db), "hook-ingest", "--event", "Stop"]) == 0
    assert len(store.list_turns(session.id)) == 1


def test_cli_hook_ingest_is_quiet_by_default(tmp_path, monkeypatch, capsys):
    db = tmp_path / "csgs.sqlite3"
    payload = {
        "session_id": "codex-session-quiet",
        "turn_id": "codex-turn-quiet",
        "cwd": str(tmp_path),
        "prompt": "Quiet hook",
    }

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["--db", str(db), "hook-ingest", "--event", "UserPromptSubmit"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_hook_ingest_can_print_result_for_debugging(tmp_path, monkeypatch, capsys):
    db = tmp_path / "csgs.sqlite3"
    payload = {
        "session_id": "codex-session-debug",
        "turn_id": "codex-turn-debug",
        "cwd": str(tmp_path),
        "prompt": "Debug hook",
    }

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["--db", str(db), "hook-ingest", "--event", "UserPromptSubmit", "--print-result"]) == 0

    captured = capsys.readouterr()
    assert '"status": "pending"' in captured.out
    assert '"codex_session_id": "codex-session-debug"' in captured.out


def test_cli_hook_ingest_uses_remote_config_when_no_db_is_explicit(tmp_path, monkeypatch, capsys):
    csgs_home = tmp_path / "csgs-home"
    monkeypatch.setenv("CSGS_HOME", str(csgs_home))
    monkeypatch.delenv("CSGS_DB", raising=False)
    write_config(mode="remote", endpoint="https://csgs.example.com")
    payload = {"session_id": "codex-remote", "turn_id": "turn-remote", "prompt": "Remote"}
    called = {}

    def fake_remote(endpoint, event, hook_payload):
        called["endpoint"] = endpoint
        called["event"] = event
        called["payload"] = hook_payload
        return {"status": "remote"}

    monkeypatch.setattr("csgs.cli.ingest_codex_hook_remote", fake_remote)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert main(["hook-ingest", "--event", "UserPromptSubmit", "--print-result"]) == 0

    assert called == {
        "endpoint": "https://csgs.example.com",
        "event": "UserPromptSubmit",
        "payload": payload,
    }
    assert '"status": "remote"' in capsys.readouterr().out
