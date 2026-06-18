from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from csgs.models import Entry, Group, Session, Turn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    project TEXT,
    codex_session_id TEXT,
    title TEXT,
    summary TEXT,
    tags TEXT,
    summary_turn_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_id TEXT,
    sync_state TEXT DEFAULT 'local'
);

CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    codex_session_id TEXT,
    codex_turn_id TEXT,
    turn_index INTEGER NOT NULL,
    prompt TEXT,
    output TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, turn_index)
);

CREATE TABLE IF NOT EXISTS pending_codex_turns (
    codex_turn_id TEXT PRIMARY KEY,
    codex_session_id TEXT NOT NULL,
    project TEXT,
    cwd TEXT,
    transcript_path TEXT,
    prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    device_id TEXT,
    kind TEXT DEFAULT 'summary',
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_state TEXT DEFAULT 'local'
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS group_projects (
    group_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, project_id)
);
"""


class CSGSStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS runs")
            conn.executescript(SCHEMA_SQL)
            self._migrate_schema(conn)

    def create_session(self, session: Session) -> Session:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if session.created_at is None:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        id, parent_id, project, codex_session_id, title, summary, tags,
                        summary_turn_index, device_id, sync_state, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        session.id,
                        session.parent_id,
                        session.project,
                        session.codex_session_id,
                        session.title,
                        session.summary,
                        self._serialize_tags(session.tags),
                        session.summary_turn_index,
                        session.device_id,
                        session.sync_state or "local",
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        id, parent_id, project, codex_session_id, title, summary, tags,
                        summary_turn_index, created_at, updated_at, device_id, sync_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?)
                    """,
                    (
                        session.id,
                        session.parent_id,
                        session.project,
                        session.codex_session_id,
                        session.title,
                        session.summary,
                        self._serialize_tags(session.tags),
                        session.summary_turn_index,
                        session.created_at,
                        session.updated_at,
                        session.device_id,
                        session.sync_state or "local",
                    ),
                )

        saved = self.get_session(session.id)
        if saved is None:
            raise RuntimeError(f"failed to persist session {session.id}")
        return saved

    def get_session(self, session_id: str) -> Session | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def get_session_by_codex_session_id(self, codex_session_id: str) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE codex_session_id = ? ORDER BY created_at, id LIMIT 1",
                (codex_session_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions(self) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at, id").fetchall()
        return [self._row_to_session(row) for row in rows]

    def list_project_sessions(self, project: str) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE project = ? ORDER BY created_at, id",
                (project,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_session_children(self, parent_id: str) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE parent_id = ? ORDER BY created_at, id",
                (parent_id,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def search_sessions(
        self,
        text: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> list[Session]:
        sessions = self.list_sessions()
        if project is not None:
            sessions = [session for session in sessions if session.project == project]
        if tags:
            required = set(tags)
            sessions = [session for session in sessions if required.issubset(set(session.tags))]
        if text:
            needle = text.lower()
            sessions = [
                session
                for session in sessions
                if self._session_matches_text(session, needle)
            ]
        return sessions

    def create_turn(self, turn: Turn) -> Turn:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if turn.created_at is None:
                conn.execute(
                    """
                    INSERT INTO turns (
                        id, session_id, codex_session_id, codex_turn_id, turn_index, prompt, output, summary
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        turn.session_id,
                        turn.codex_session_id,
                        turn.codex_turn_id,
                        turn.turn_index,
                        turn.prompt,
                        turn.output,
                        turn.summary,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO turns (
                        id, session_id, codex_session_id, codex_turn_id,
                        turn_index, prompt, output, summary, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        turn.session_id,
                        turn.codex_session_id,
                        turn.codex_turn_id,
                        turn.turn_index,
                        turn.prompt,
                        turn.output,
                        turn.summary,
                        turn.created_at,
                    ),
                )

        saved = self.get_turn(turn.id)
        if saved is None:
            raise RuntimeError(f"failed to persist turn {turn.id}")
        return saved

    def create_entry(self, entry: Entry) -> Entry:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if entry.created_at is None:
                conn.execute(
                    """
                    INSERT INTO entries (
                        id, project_id, session_id, device_id, kind, summary, sync_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.project_id,
                        entry.session_id,
                        entry.device_id,
                        entry.kind,
                        entry.summary,
                        entry.sync_state or "local",
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO entries (
                        id, project_id, session_id, device_id, kind, summary, created_at, sync_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.project_id,
                        entry.session_id,
                        entry.device_id,
                        entry.kind,
                        entry.summary,
                        entry.created_at,
                        entry.sync_state or "local",
                    ),
                )
        saved = self.get_entry(entry.id)
        if saved is None:
            raise RuntimeError(f"failed to persist entry {entry.id}")
        return saved

    def get_entry(self, entry_id: str) -> Entry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_entries(self, session_id: str) -> list[Entry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def list_project_entries(self, project_id: str) -> list[Entry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE project_id = ? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def upsert_group(self, group: Group) -> Group:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO groups (id, name)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = COALESCE(excluded.name, groups.name)
                """,
                (group.id, group.name),
            )
        saved = self.get_group(group.id)
        if saved is None:
            raise RuntimeError(f"failed to persist group {group.id}")
        return saved

    def get_group(self, group_id: str) -> Group | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_group(row)

    def add_group_project(self, group_id: str, project_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO group_projects (group_id, project_id)
                VALUES (?, ?)
                """,
                (group_id, project_id),
            )

    def list_group_project_ids(self, group_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id FROM group_projects WHERE group_id = ? ORDER BY created_at, project_id",
                (group_id,),
            ).fetchall()
        return [str(row["project_id"]) for row in rows]

    def get_turn(self, turn_id: str) -> Turn | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_turn(row)

    def get_turn_by_codex_turn_id(self, codex_turn_id: str) -> Turn | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM turns WHERE codex_turn_id = ? ORDER BY created_at, id LIMIT 1",
                (codex_turn_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_turn(row)

    def list_turns(self, session_id: str) -> list[Turn]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_index, created_at, id",
                (session_id,),
            ).fetchall()
        return [self._row_to_turn(row) for row in rows]

    def next_turn_index(self, session_id: str) -> int:
        with self._connect() as conn:
            value = conn.execute(
                "SELECT COALESCE(MAX(turn_index), 0) + 1 FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
        return int(value)

    def upsert_pending_codex_turn(
        self,
        *,
        codex_session_id: str,
        codex_turn_id: str,
        project: str | None,
        cwd: str | None,
        transcript_path: str | None,
        prompt: str,
    ) -> dict[str, str | None]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_codex_turns (
                    codex_turn_id, codex_session_id, project, cwd, transcript_path, prompt, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(codex_turn_id) DO UPDATE SET
                    codex_session_id = excluded.codex_session_id,
                    project = excluded.project,
                    cwd = excluded.cwd,
                    transcript_path = excluded.transcript_path,
                    prompt = excluded.prompt,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (codex_turn_id, codex_session_id, project, cwd, transcript_path, prompt),
            )
        pending = self.get_pending_codex_turn(codex_turn_id)
        if pending is None:
            raise RuntimeError(f"failed to persist pending Codex turn {codex_turn_id}")
        return pending

    def get_pending_codex_turn(self, codex_turn_id: str) -> dict[str, str | None] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_codex_turns WHERE codex_turn_id = ?",
                (codex_turn_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "codex_turn_id": row["codex_turn_id"],
            "codex_session_id": row["codex_session_id"],
            "project": row["project"],
            "cwd": row["cwd"],
            "transcript_path": row["transcript_path"],
            "prompt": row["prompt"],
        }

    def delete_pending_codex_turn(self, codex_turn_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_codex_turns WHERE codex_turn_id = ?", (codex_turn_id,))

    def update_session_summary(
        self,
        session_id: str,
        summary: str,
        summary_turn_index: int,
    ) -> Session:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET summary = ?, summary_turn_index = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (summary, summary_turn_index, session_id),
            )
        saved = self.get_session(session_id)
        if saved is None:
            raise RuntimeError(f"failed to update session {session_id}")
        return saved

    def update_session_codex_session_id(self, session_id: str, codex_session_id: str) -> Session:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET codex_session_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (codex_session_id, session_id),
            )
        saved = self.get_session(session_id)
        if saved is None:
            raise RuntimeError(f"failed to update session {session_id}")
        return saved

    def _session_matches_text(self, session: Session, needle: str) -> bool:
        turns = self.list_turns(session.id)
        entries = self.list_entries(session.id)
        fields = [session.title or "", session.summary, session.codex_session_id or ""]
        fields.extend(turn.prompt for turn in turns)
        fields.extend(turn.output for turn in turns)
        fields.extend(turn.summary for turn in turns)
        fields.extend(turn.codex_session_id or "" for turn in turns)
        fields.extend(entry.summary for entry in entries)
        return any(needle in field.lower() for field in fields)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        CSGSStore._ensure_column(
            conn,
            table="sessions",
            column="codex_session_id",
            statement="ALTER TABLE sessions ADD COLUMN codex_session_id TEXT",
        )
        CSGSStore._ensure_column(
            conn,
            table="turns",
            column="codex_session_id",
            statement="ALTER TABLE turns ADD COLUMN codex_session_id TEXT",
        )
        CSGSStore._ensure_column(
            conn,
            table="turns",
            column="codex_turn_id",
            statement="ALTER TABLE turns ADD COLUMN codex_turn_id TEXT",
        )
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                device_id TEXT,
                kind TEXT DEFAULT 'summary',
                summary TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_state TEXT DEFAULT 'local'
            );

            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS group_projects (
                group_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, project_id)
            );
            """
        )

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, statement: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(statement)

    @staticmethod
    def _serialize_tags(tags: list[str]) -> str:
        return ",".join(tag.strip() for tag in tags if tag.strip())

    @staticmethod
    def _deserialize_tags(tags: str | None) -> list[str]:
        if not tags:
            return []
        return [tag for tag in tags.split(",") if tag]

    @classmethod
    def _row_to_session(cls, row: sqlite3.Row | dict[str, Any]) -> Session:
        return Session(
            id=row["id"],
            parent_id=row["parent_id"],
            project=row["project"],
            codex_session_id=row["codex_session_id"],
            title=row["title"],
            summary=row["summary"],
            tags=cls._deserialize_tags(row["tags"]),
            summary_turn_index=int(row["summary_turn_index"] or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            device_id=row["device_id"],
            sync_state=row["sync_state"],
        )

    @staticmethod
    def _row_to_turn(row: sqlite3.Row | dict[str, Any]) -> Turn:
        return Turn(
            id=row["id"],
            session_id=row["session_id"],
            codex_session_id=row["codex_session_id"],
            codex_turn_id=row["codex_turn_id"],
            turn_index=int(row["turn_index"]),
            prompt=row["prompt"],
            output=row["output"],
            summary=row["summary"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_entry(row: sqlite3.Row | dict[str, Any]) -> Entry:
        return Entry(
            id=row["id"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            device_id=row["device_id"],
            kind=row["kind"],
            summary=row["summary"],
            created_at=row["created_at"],
            sync_state=row["sync_state"],
        )

    @staticmethod
    def _row_to_group(row: sqlite3.Row | dict[str, Any]) -> Group:
        return Group(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
        )
