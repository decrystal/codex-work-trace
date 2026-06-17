from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from csgs.models import Run


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


class RunStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def create_run(self, run: Run) -> Run:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if run.created_at is None:
                conn.execute(
                    """
                    INSERT INTO runs (id, parent_id, project, prompt, output, summary, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.id,
                        run.parent_id,
                        run.project,
                        run.prompt,
                        run.output,
                        run.summary,
                        self._serialize_tags(run.tags),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO runs (id, parent_id, project, prompt, output, summary, tags, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        )
