from csgs.models import Run
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
