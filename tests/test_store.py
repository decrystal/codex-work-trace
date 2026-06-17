from csgs.models import Run
from csgs.store import RunStore


def test_store_initializes_schema_and_persists_run(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()

    run = Run(
        id="A_001",
        parent_id=None,
        project="demo",
        prompt="Refactor the parser",
        output="Changed parser module",
        summary="Refactored parser module.",
        tags=["refactor"],
    )

    store.create_run(run)

    saved = store.get_run("A_001")
    assert saved is not None
    assert saved.id == "A_001"
    assert saved.project == "demo"
    assert saved.tags == ["refactor"]


def test_store_adds_sync_metadata_columns(tmp_path):
    store = RunStore(tmp_path / "csgs.sqlite3")
    store.init_schema()

    run = Run(
        id="A_001",
        parent_id=None,
        project="demo",
        prompt="Root",
        output="Output",
        summary="Summary.",
        tags=["idea"],
        device_id="local-device",
        sync_state="local",
    )

    saved = store.create_run(run)

    assert saved.device_id == "local-device"
    assert saved.sync_state == "local"
    assert saved.updated_at is not None
    assert [item.id for item in store.list_project_runs("demo")] == ["A_001"]
