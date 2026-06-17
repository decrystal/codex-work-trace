from __future__ import annotations

from uuid import uuid4

from csgs.errors import RunAlreadyExistsError, RunNotFoundError
from csgs.models import Run
from csgs.store import RunStore
from csgs.summary import generate_summary


class SessionGraphService:
    def __init__(self, store: RunStore):
        self.store = store
        self.store.init_schema()

    def log_run(
        self,
        prompt: str,
        output: str,
        parent_id: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        run_id: str | None = None,
    ) -> Run:
        if parent_id is not None and self.store.get_run(parent_id) is None:
            raise RunNotFoundError(parent_id)

        chosen_id = run_id or self._new_run_id()
        if self.store.get_run(chosen_id) is not None:
            raise RunAlreadyExistsError(chosen_id)

        run = Run(
            id=chosen_id,
            parent_id=parent_id,
            project=project,
            prompt=prompt,
            output=output,
            summary=generate_summary(prompt, output),
            tags=tags or [],
        )
        return self.store.create_run(run)

    def get_run(self, run_id: str) -> Run:
        run = self.store.get_run(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    def _new_run_id(self) -> str:
        while True:
            run_id = f"R_{uuid4().hex[:12]}"
            if self.store.get_run(run_id) is None:
                return run_id
