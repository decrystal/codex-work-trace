import asyncio

from csgs import mcp_server


def test_mcp_log_and_get_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CSGS_DB", str(tmp_path / "csgs.sqlite3"))

    created = asyncio.run(mcp_server.log_run(prompt="Root", output="Root output", run_id="A_001"))
    fetched = asyncio.run(mcp_server.get_run("A_001"))

    assert created["id"] == "A_001"
    assert fetched["summary"] == created["summary"]
