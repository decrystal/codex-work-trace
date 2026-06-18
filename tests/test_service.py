from csgs.service import SessionGraphService
from csgs.store import CSGSStore


def test_log_session_generates_summary_and_id(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))

    session = service.log_session(
        project="csgs",
        codex_session_id="codex-session-123",
        turns=[{"prompt": "Please add search for sessions", "output": "Implemented search over summaries."}],
        tags=["idea", "search"],
    )

    assert session.id.startswith("S_")
    assert session.codex_session_id == "codex-session-123"
    assert "search" in session.summary.lower()
    assert len([s for s in session.summary.split(".") if s.strip()]) <= 5
    assert service.get_session(session.id).summary == session.summary
    assert len(service.list_turns(session.id)) == 1


def test_fork_links_new_session_to_source(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))
    root = service.log_session(
        project="alpha",
        codex_session_id="codex-root",
        turns=[{"prompt": "Start parser idea", "output": "Created parser notes."}],
        session_id="S_001",
    )

    child = service.fork_session(
        root.id,
        turns=[{"prompt": "Try CLI shape", "output": "Added CLI sketch."}],
        codex_session_id="codex-child",
        session_id="S_002",
    )

    assert child.parent_id == "S_001"
    assert child.codex_session_id == "codex-child"
    assert service.get_session("S_001").parent_id is None


def test_trace_renders_origin_tree(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))
    service.log_session("alpha", [{"prompt": "Root", "output": "Root output"}], session_id="S_000")
    service.log_session("alpha", [{"prompt": "Main path", "output": "Main output"}], parent_id="S_000", session_id="S_001")
    service.log_session("alpha", [{"prompt": "Branch B", "output": "Branch output"}], parent_id="S_001", session_id="S_002")
    service.log_session("alpha", [{"prompt": "Branch C", "output": "Branch output"}], parent_id="S_001", session_id="S_003")

    trace = service.trace_session("S_002")

    assert "S_000" in trace
    assert "S_001" in trace
    assert "S_002" in trace
    assert "S_003" in trace
    assert "└── S_001" in trace


def test_search_filters_by_text_tag_and_project(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))
    service.log_session("alpha", [{"prompt": "Parser work", "output": "Added tokenizer."}], tags=["refactor"], session_id="S_001")
    service.log_session("beta", [{"prompt": "UI work", "output": "Added graph search."}], tags=["idea"], session_id="S_002")

    results = service.search_sessions(text="graph", tags=["idea"], project="beta")

    assert [session.id for session in results] == ["S_002"]
