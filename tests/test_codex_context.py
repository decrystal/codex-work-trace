from csgs.codex_context import current_codex_session_id


def test_current_codex_session_id_reads_codex_thread_id():
    session_id = current_codex_session_id({"CODEX_THREAD_ID": "thread-123"})

    assert session_id == "thread-123"


def test_current_codex_session_id_ignores_blank_values():
    session_id = current_codex_session_id({"CODEX_THREAD_ID": "  "})

    assert session_id is None
