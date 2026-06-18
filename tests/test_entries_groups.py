from csgs.service import SessionGraphService, derive_project
from csgs.store import CSGSStore
from csgs.sync import export_project, import_sessions


def test_derive_project_uses_path_when_folder_has_no_git(tmp_path):
    folder = tmp_path / "notes"
    folder.mkdir()

    assert derive_project(str(folder)) == f"path:{folder}"


def test_record_summary_appends_entries_and_updates_session_summary(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))

    first = service.record_summary(
        summary="Implemented local record-summary.",
        cwd=str(tmp_path),
        codex_session_id="codex-thread-1",
        title="CSGS work",
    )
    second = service.record_summary(
        summary="Added project-first entries.",
        cwd=str(tmp_path),
        codex_session_id="codex-thread-1",
        title="CSGS work",
    )

    session = service.get_session(first.session_id)
    entries = service.list_entries(session.id)

    assert first.id != second.id
    assert first.project_id == f"path:{tmp_path}"
    assert second.session_id == first.session_id
    assert [entry.summary for entry in entries] == [
        "Implemented local record-summary.",
        "Added project-first entries.",
    ]
    assert "Implemented local record-summary" in session.summary
    assert "Added project-first entries" in session.summary
    assert session.summary_turn_index == 2


def test_groups_associate_multiple_projects_and_query_entries(tmp_path):
    service = SessionGraphService(CSGSStore(tmp_path / "csgs.sqlite3"))
    service.add_group_project("csgs", "github:decrytal-ade/codex-work-trace", name="CSGS")
    service.add_group_project("csgs", "github:decrytal-ade/csgs-docs", name="CSGS")

    service.record_summary(
        summary="Core implementation.",
        project_id="github:decrytal-ade/codex-work-trace",
        codex_session_id="codex-core",
    )
    service.record_summary(
        summary="Docs implementation.",
        project_id="github:decrytal-ade/csgs-docs",
        codex_session_id="codex-docs",
    )

    entries = service.list_group_entries("csgs")

    assert [entry.summary for entry in entries] == ["Core implementation.", "Docs implementation."]


def test_sync_exports_and_imports_entries_append_only(tmp_path):
    source_store = CSGSStore(tmp_path / "source.sqlite3")
    target_store = CSGSStore(tmp_path / "target.sqlite3")
    service = SessionGraphService(source_store)
    target_store.init_schema()

    service.record_summary(
        summary="Synced entry.",
        project_id="github:decrytal-ade/codex-work-trace",
        codex_session_id="codex-sync",
    )
    payload = export_project(source_store, "github:decrytal-ade/codex-work-trace")

    first = import_sessions(target_store, payload)
    second = import_sessions(target_store, payload)

    target_service = SessionGraphService(target_store)
    entries = target_service.list_project_entries("github:decrytal-ade/codex-work-trace")

    assert len(payload["entries"]) == 1
    assert first == {"imported": 2, "skipped": 0}
    assert second == {"imported": 0, "skipped": 2}
    assert [entry.summary for entry in entries] == ["Synced entry."]
