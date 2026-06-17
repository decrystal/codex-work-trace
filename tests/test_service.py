from csgs.service import SessionGraphService
from csgs.store import RunStore


def test_log_run_generates_summary_and_id(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))

    run = service.log_run(
        prompt="Please add search for runs",
        output="Implemented search over prompt and summary.",
        project="csgs",
        tags=["idea", "search"],
    )

    assert run.id.startswith("R_")
    assert "search" in run.summary.lower()
    assert len([s for s in run.summary.split(".") if s.strip()]) <= 5
    assert service.get_run(run.id).summary == run.summary
    assert service.get_session(run.id).summary == run.summary
    assert len(service.list_turns(run.id)) == 1


def test_fork_links_new_run_to_source(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))
    root = service.log_run("Start parser idea", "Created parser notes.", run_id="A_001")

    child = service.fork_run(root.id, prompt="Try CLI shape", output="Added CLI sketch.", run_id="B_002")

    assert child.parent_id == "A_001"
    assert service.get_run("A_001").parent_id is None


def test_trace_renders_origin_tree(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))
    service.log_run("Root", "Root output", run_id="A_000")
    service.log_run("Main path", "Main output", parent_id="A_000", run_id="A_001")
    service.log_run("Branch B", "Branch output", parent_id="A_001", run_id="B_002")
    service.log_run("Branch C", "Branch output", parent_id="A_001", run_id="C_003")

    trace = service.trace_run("B_002")

    assert "A_000" in trace
    assert "A_001" in trace
    assert "B_002" in trace
    assert "C_003" in trace
    assert "└── A_001" in trace


def test_search_filters_by_text_tag_and_project(tmp_path):
    service = SessionGraphService(RunStore(tmp_path / "csgs.sqlite3"))
    service.log_run("Parser work", "Added tokenizer.", project="alpha", tags=["refactor"], run_id="A_001")
    service.log_run("UI work", "Added graph search.", project="beta", tags=["idea"], run_id="B_001")

    results = service.search_runs(text="graph", tags=["idea"], project="beta")

    assert [run.id for run in results] == ["B_001"]
