import sqlite3

from csgs.models import Session
from csgs.store import CSGSStore


def test_store_initializes_session_only_schema(tmp_path):
    db = tmp_path / "csgs.sqlite3"
    store = CSGSStore(db)
    store.init_schema()

    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }

    assert "sessions" in tables
    assert "turns" in tables
    assert "runs" not in tables


def test_store_drops_legacy_runs_table(tmp_path):
    db = tmp_path / "csgs.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO runs (id) VALUES ('A_001')")

    store = CSGSStore(db)
    store.init_schema()

    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert "runs" not in tables


def test_store_migrates_codex_session_id_columns(tmp_path):
    db = tmp_path / "csgs.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                project TEXT,
                title TEXT,
                summary TEXT,
                tags TEXT,
                summary_turn_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT,
                sync_state TEXT DEFAULT 'local'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE turns (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                prompt TEXT,
                output TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, turn_index)
            )
            """
        )

    store = CSGSStore(db)
    store.init_schema()

    with sqlite3.connect(db) as conn:
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        turn_columns = {row[1] for row in conn.execute("PRAGMA table_info(turns)")}

    assert "codex_session_id" in session_columns
    assert "codex_session_id" in turn_columns


def test_store_persists_session_sync_metadata(tmp_path):
    store = CSGSStore(tmp_path / "csgs.sqlite3")
    store.init_schema()

    session = Session(
        id="S_001",
        parent_id=None,
        project="demo",
        title="Root",
        summary="Session summary.",
        tags=["idea"],
        summary_turn_index=1,
        codex_session_id="codex-session-123",
        device_id="local-device",
        sync_state="local",
    )

    saved = store.create_session(session)

    assert saved.codex_session_id == "codex-session-123"
    assert saved.device_id == "local-device"
    assert saved.sync_state == "local"
    assert saved.updated_at is not None
    assert [item.id for item in store.list_project_sessions("demo")] == ["S_001"]
