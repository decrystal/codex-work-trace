from csgs.models import Session, Turn
from csgs.store import RunStore


def test_store_persists_session_and_turns(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()

    session = store.create_session(
        Session(
            id="S_001",
            parent_id=None,
            project="demo",
            title="CSGS design",
            summary="Initial session summary.",
            tags=["architecture"],
            summary_turn_index=1,
        )
    )
    first = store.create_turn(
        Turn(
            id="T_001",
            session_id=session.id,
            turn_index=1,
            prompt="Design the system",
            output="Created the design",
            summary="Designed the system.",
        )
    )
    second = store.create_turn(
        Turn(
            id="T_002",
            session_id=session.id,
            turn_index=2,
            prompt="Add sync",
            output="Added sync",
            summary="Added sync.",
        )
    )

    updated = store.update_session_summary("S_001", "Updated through turn two.", 2)

    assert store.get_session("S_001").summary == "Updated through turn two."
    assert updated.summary_turn_index == 2
    assert [turn.id for turn in store.list_turns("S_001")] == [first.id, second.id]
    assert store.next_turn_index("S_001") == 3
