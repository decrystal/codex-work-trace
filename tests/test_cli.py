from csgs.cli import main


def test_cli_log_and_trace(tmp_path, capsys):
    db = tmp_path / "csgs.sqlite3"

    assert main(["--db", str(db), "log", "--id", "A_001", "--prompt", "Root", "--output", "Root output"]) == 0
    assert main(["--db", str(db), "fork", "A_001", "--id", "B_002", "--prompt", "Child", "--output", "Child output"]) == 0
    assert main(["--db", str(db), "trace", "B_002"]) == 0

    captured = capsys.readouterr()
    assert "A_001" in captured.out
    assert "B_002" in captured.out


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
    assert '"summary_turn_index": 2' in captured.out
