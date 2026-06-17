from csgs.service import SessionGraphService
from csgs.store import RunStore


def test_log_session_records_multiple_turns_and_summary_index(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))

    session = service.log_session(
        project="demo",
        title="CSGS architecture",
        turns=[
            {"prompt": "Design MVP", "output": "Built SQLite and MCP stub"},
            {"prompt": "Switch to HTTP MCP", "output": "Added local daemon and sync export"},
        ],
        tags=["architecture"],
        session_id="S_001",
    )

    turns = service.list_turns("S_001")

    assert session.id == "S_001"
    assert session.summary_turn_index == 2
    assert len(turns) == 2
    assert turns[0].turn_index == 1
    assert turns[1].turn_index == 2
    assert "HTTP MCP" in session.summary


def test_append_turn_updates_session_summary_incrementally(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))
    service.log_session(
        project="demo",
        title="CSGS architecture",
        turns=[{"prompt": "Design MVP", "output": "Built SQLite and MCP stub"}],
        session_id="S_001",
    )
    before = service.get_session("S_001")

    turn = service.append_turn(
        "S_001",
        prompt="Clarify session semantics",
        output="Changed graph node to full session and turns to inner records",
    )
    after = service.get_session("S_001")

    assert turn.turn_index == 2
    assert after.summary_turn_index == 2
    assert before.summary in after.summary
    assert "Clarify session semantics" in after.summary
