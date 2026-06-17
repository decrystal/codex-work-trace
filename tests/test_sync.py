from csgs.models import Run
from csgs.service import SessionGraphService
from csgs.store import RunStore
from csgs.sync import export_project, import_runs


def test_export_project_only_includes_matching_project(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()
    store.create_run(Run("A_001", None, "alpha", "Prompt", "Output", "Summary.", ["idea"]))
    store.create_run(Run("B_001", None, "beta", "Prompt", "Output", "Summary.", ["idea"]))

    payload = export_project(store, "alpha")

    assert payload["project"] == "alpha"
    assert [run["id"] for run in payload["runs"]] == ["A_001"]


def test_import_runs_skips_existing_ids(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()
    store.create_run(Run("A_001", None, "alpha", "Prompt", "Output", "Summary.", ["idea"]))

    result = import_runs(
        store,
        {
            "project": "alpha",
            "runs": [
                {
                    "id": "A_001",
                    "parent_id": None,
                    "project": "alpha",
                    "prompt": "Old",
                    "output": "Old",
                    "summary": "Old.",
                    "tags": [],
                },
                {
                    "id": "A_002",
                    "parent_id": "A_001",
                    "project": "alpha",
                    "prompt": "New",
                    "output": "New",
                    "summary": "New.",
                    "tags": ["sync"],
                },
            ],
        },
    )

    assert result == {"imported": 1, "skipped": 1}
    assert store.get_run("A_002").parent_id == "A_001"


def test_export_project_includes_sessions_and_turns(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    service = SessionGraphService(store)
    service.log_session(
        project="alpha",
        title="Alpha session",
        turns=[{"prompt": "Prompt", "output": "Output"}],
        session_id="S_001",
    )
    service.log_session(
        project="beta",
        title="Beta session",
        turns=[{"prompt": "Prompt", "output": "Output"}],
        session_id="S_002",
    )

    payload = export_project(store, "alpha")

    assert [session["id"] for session in payload["sessions"]] == ["S_001"]
    assert [turn["session_id"] for turn in payload["turns"]] == ["S_001"]


def test_import_runs_imports_sessions_and_turns_append_only(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    service = SessionGraphService(store)
    service.log_session(
        project="alpha",
        title="Existing",
        turns=[{"prompt": "Old", "output": "Old"}],
        session_id="S_001",
    )

    result = import_runs(
        store,
        {
            "project": "alpha",
            "sessions": [
                {
                    "id": "S_001",
                    "parent_id": None,
                    "project": "alpha",
                    "title": "Existing rewritten",
                    "summary": "Should not overwrite.",
                    "tags": [],
                    "summary_turn_index": 1,
                },
                {
                    "id": "S_002",
                    "parent_id": "S_001",
                    "project": "alpha",
                    "title": "Imported",
                    "summary": "Imported summary.",
                    "tags": ["sync"],
                    "summary_turn_index": 1,
                },
            ],
            "turns": [
                {
                    "id": "T_002",
                    "session_id": "S_002",
                    "turn_index": 1,
                    "prompt": "Imported",
                    "output": "Imported",
                    "summary": "Imported turn.",
                }
            ],
        },
    )

    assert result == {"imported": 2, "skipped": 1}
    assert store.get_session("S_001").title == "Existing"
    assert store.get_session("S_002").parent_id == "S_001"
    assert store.list_turns("S_002")[0].summary == "Imported turn."
