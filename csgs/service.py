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

    def fork_run(
        self,
        source_id: str,
        prompt: str | None = None,
        output: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        run_id: str | None = None,
    ) -> Run:
        source = self.get_run(source_id)
        return self.log_run(
            prompt=prompt if prompt is not None else source.prompt,
            output=output if output is not None else source.output,
            parent_id=source.id,
            project=project if project is not None else source.project,
            tags=tags if tags is not None else source.tags,
            run_id=run_id,
        )

    def search_runs(
        self,
        text: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> list[Run]:
        return self.store.search_runs(text=text, tags=tags, project=project)

    def trace_run(self, run_id: str) -> str:
        target = self.get_run(run_id)
        root = self._find_root(target)
        lines = [root.id]
        lines.extend(self._render_children(root.id, prefix=""))
        return "\n".join(lines)

    def _new_run_id(self) -> str:
        while True:
            run_id = f"R_{uuid4().hex[:12]}"
            if self.store.get_run(run_id) is None:
                return run_id

    def _find_root(self, run: Run) -> Run:
        seen = {run.id}
        current = run
        while current.parent_id is not None:
            if current.parent_id in seen:
                break
            seen.add(current.parent_id)
            current = self.get_run(current.parent_id)
        return current

    def _render_children(self, parent_id: str, prefix: str) -> list[str]:
        children = self.store.get_children(parent_id)
        lines: list[str] = []
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix} {connector}{child.id}")
            extension = "    " if is_last else "│   "
            lines.extend(self._render_children(child.id, prefix=f"{prefix} {extension}"))
        return lines
