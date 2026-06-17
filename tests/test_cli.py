from csgs.cli import main


def test_cli_log_and_trace(tmp_path, capsys):
    db = tmp_path / "csgs.sqlite3"

    assert main(["--db", str(db), "log", "--id", "A_001", "--prompt", "Root", "--output", "Root output"]) == 0
    assert main(["--db", str(db), "fork", "A_001", "--id", "B_002", "--prompt", "Child", "--output", "Child output"]) == 0
    assert main(["--db", str(db), "trace", "B_002"]) == 0

    captured = capsys.readouterr()
    assert "A_001" in captured.out
    assert "B_002" in captured.out
