from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from csgs.models import Run, Session, Turn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    project TEXT,
    prompt TEXT,
    output TEXT,
    summary TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SESSION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
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
);

CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    prompt TEXT,
    output TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, turn_index)
);
"""

MIGRATIONS = {
    "device_id": "ALTER TABLE runs ADD COLUMN device_id TEXT",
    "updated_at": "ALTER TABLE runs ADD COLUMN updated_at TIMESTAMP",
    "sync_state": "ALTER TABLE runs ADD COLUMN sync_state TEXT DEFAULT 'local'",
}


class RunStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.executescript(SESSION_SCHEMA_SQL)
            self._migrate_schema(conn)

    def create_session(self, session: Session) -> Session:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if session.created_at is None:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        id, parent_id, project, title, summary, tags,
                        summary_turn_index, device_id, sync_state, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        session.id,
                        session.parent_id,
                        session.project,
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
                        id, parent_id, project, title, summary, tags,
                        summary_turn_index, created_at, updated_at, device_id, sync_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?)
                    """,
                    (
                        session.id,
                        session.parent_id,
                        session.project,
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

    def create_turn(self, turn: Turn) -> Turn:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if turn.created_at is None:
                conn.execute(
                    """
                    INSERT INTO turns (id, session_id, turn_index, prompt, output, summary)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (turn.id, turn.session_id, turn.turn_index, turn.prompt, turn.output, turn.summary),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO turns (id, session_id, turn_index, prompt, output, summary, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        turn.session_id,
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

    def get_turn(self, turn_id: str) -> Turn | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone()
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

    def create_run(self, run: Run) -> Run:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if run.created_at is None:
                conn.execute(
                    """
                    INSERT INTO runs (
                        id, parent_id, project, prompt, output, summary, tags,
                        device_id, sync_state, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        run.id,
                        run.parent_id,
                        run.project,
                        run.prompt,
                        run.output,
                        run.summary,
                        self._serialize_tags(run.tags),
                        run.device_id,
                        run.sync_state or "local",
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO runs (
                        id, parent_id, project, prompt, output, summary, tags,
                        created_at, device_id, sync_state, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                    """,
                    (
                        run.id,
                        run.parent_id,
                        run.project,
                        run.prompt,
                        run.output,
                        run.summary,
                        self._serialize_tags(run.tags),
                        run.created_at,
                        run.device_id,
                        run.sync_state or "local",
                        run.updated_at,
                    ),
                )

        saved = self.get_run(run.id)
        if saved is None:
            raise RuntimeError(f"failed to persist run {run.id}")
        return saved

    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self) -> list[Run]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at, id").fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_children(self, parent_id: str) -> list[Run]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE parent_id = ? ORDER BY created_at, id",
                (parent_id,),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_session_children(self, parent_id: str) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE parent_id = ? ORDER BY created_at, id",
                (parent_id,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def list_project_sessions(self, project: str) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE project = ? ORDER BY created_at, id",
                (project,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def list_project_runs(self, project: str) -> list[Run]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE project = ? ORDER BY created_at, id",
                (project,),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def search_runs(
        self,
        text: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> list[Run]:
        runs = self.list_runs()
        if project is not None:
            runs = [run for run in runs if run.project == project]
        if text:
            needle = text.lower()
            runs = [
                run
                for run in runs
                if needle in run.prompt.lower() or needle in run.summary.lower()
            ]
        if tags:
            required = set(tags)
            runs = [run for run in runs if required.issubset(set(run.tags))]
        return runs

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        for column, statement in MIGRATIONS.items():
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
    def _row_to_run(cls, row: sqlite3.Row | dict[str, Any]) -> Run:
        return Run(
            id=row["id"],
            parent_id=row["parent_id"],
            project=row["project"],
            prompt=row["prompt"],
            output=row["output"],
            summary=row["summary"],
            tags=cls._deserialize_tags(row["tags"]),
            created_at=row["created_at"],
            device_id=row["device_id"],
            updated_at=row["updated_at"],
            sync_state=row["sync_state"],
        )

    @classmethod
    def _row_to_session(cls, row: sqlite3.Row | dict[str, Any]) -> Session:
        return Session(
            id=row["id"],
            parent_id=row["parent_id"],
            project=row["project"],
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
            turn_index=int(row["turn_index"]),
            prompt=row["prompt"],
            output=row["output"],
            summary=row["summary"],
            created_at=row["created_at"],
        )
