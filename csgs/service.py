from __future__ import annotations

from uuid import uuid4

from csgs.errors import RunAlreadyExistsError, RunNotFoundError
from csgs.models import Run, Session, Turn
from csgs.store import RunStore
from csgs.summary import generate_summary, summarize_session_increment


class SessionGraphService:
    def __init__(self, store: RunStore):
        self.store = store
        self.store.init_schema()

    def log_session(
        self,
        project: str | None,
        turns: list[dict[str, str]],
        parent_id: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        if parent_id is not None and self.store.get_session(parent_id) is None:
            raise RunNotFoundError(parent_id)

        chosen_id = session_id or self._new_session_id()
        if self.store.get_session(chosen_id) is not None:
            raise RunAlreadyExistsError(chosen_id)

        session = self.store.create_session(
            Session(
                id=chosen_id,
                parent_id=parent_id,
                project=project,
                title=title,
                summary="",
                tags=tags or [],
                summary_turn_index=0,
            )
        )

        for turn in turns:
            self.append_turn(
                session.id,
                prompt=turn.get("prompt", ""),
                output=turn.get("output", ""),
            )

        return self.get_session(session.id)

    def append_turn(self, session_id: str, prompt: str, output: str) -> Turn:
        session = self.get_session(session_id)
        turn_index = self.store.next_turn_index(session_id)
        turn = self.store.create_turn(
            Turn(
                id=self._new_turn_id(),
                session_id=session_id,
                turn_index=turn_index,
                prompt=prompt,
                output=output,
                summary=generate_summary(prompt, output),
            )
        )
        next_summary = summarize_session_increment(session.summary, turn.summary)
        self.store.update_session_summary(session_id, next_summary, turn.turn_index)
        return turn

    def get_session(self, session_id: str) -> Session:
        session = self.store.get_session(session_id)
        if session is None:
            raise RunNotFoundError(session_id)
        return session

    def list_turns(self, session_id: str) -> list[Turn]:
        self.get_session(session_id)
        return self.store.list_turns(session_id)

    def trace_session(self, session_id: str) -> str:
        target = self.get_session(session_id)
        root = self._find_session_root(target)
        lines = [root.id]
        lines.extend(self._render_session_children(root.id, prefix=""))
        return "\n".join(lines)

    def log_run(
        self,
        prompt: str,
        output: str,
        parent_id: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        run_id: str | None = None,
    ) -> Run:
        if (
            parent_id is not None
            and self.store.get_session(parent_id) is None
            and self.store.get_run(parent_id) is None
        ):
            raise RunNotFoundError(parent_id)

        chosen_id = run_id or self._new_run_id()
        if self.store.get_session(chosen_id) is not None or self.store.get_run(chosen_id) is not None:
            raise RunAlreadyExistsError(chosen_id)

        session = self.log_session(
            session_id=chosen_id,
            parent_id=parent_id,
            project=project,
            tags=tags or [],
            title=None,
            turns=[{"prompt": prompt, "output": output}],
        )
        return self._session_to_run(session)

    def get_run(self, run_id: str) -> Run:
        session = self.store.get_session(run_id)
        if session is not None:
            return self._session_to_run(session)
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
        runs = self.store.search_runs(text=text, tags=tags, project=project)
        session_runs = [self._session_to_run(session) for session in self.store.list_sessions()]
        if project is not None:
            session_runs = [run for run in session_runs if run.project == project]
        if text:
            needle = text.lower()
            session_runs = [
                run
                for run in session_runs
                if needle in run.prompt.lower() or needle in run.output.lower() or needle in run.summary.lower()
            ]
        if tags:
            required = set(tags)
            session_runs = [run for run in session_runs if required.issubset(set(run.tags))]
        return runs + session_runs

    def trace_run(self, run_id: str) -> str:
        if self.store.get_session(run_id) is not None:
            return self.trace_session(run_id)
        target = self.get_run(run_id)
        root = self._find_root(target)
        lines = [root.id]
        lines.extend(self._render_children(root.id, prefix=""))
        return "\n".join(lines)

    def _new_run_id(self) -> str:
        while True:
            run_id = f"R_{uuid4().hex[:12]}"
            if self.store.get_run(run_id) is None and self.store.get_session(run_id) is None:
                return run_id

    def _new_session_id(self) -> str:
        while True:
            session_id = f"S_{uuid4().hex[:12]}"
            if self.store.get_session(session_id) is None:
                return session_id

    def _new_turn_id(self) -> str:
        while True:
            turn_id = f"T_{uuid4().hex[:12]}"
            if self.store.get_turn(turn_id) is None:
                return turn_id

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

    def _find_session_root(self, session: Session) -> Session:
        seen = {session.id}
        current = session
        while current.parent_id is not None:
            if current.parent_id in seen:
                break
            seen.add(current.parent_id)
            current = self.get_session(current.parent_id)
        return current

    def _render_session_children(self, parent_id: str, prefix: str) -> list[str]:
        children = self.store.get_session_children(parent_id)
        lines: list[str] = []
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix} {connector}{child.id}")
            extension = "    " if is_last else "│   "
            lines.extend(self._render_session_children(child.id, prefix=f"{prefix} {extension}"))
        return lines

    def _session_to_run(self, session: Session) -> Run:
        turns = self.store.list_turns(session.id)
        prompt = "\n\n".join(turn.prompt for turn in turns)
        output = "\n\n".join(turn.output for turn in turns)
        return Run(
            id=session.id,
            parent_id=session.parent_id,
            project=session.project,
            prompt=prompt,
            output=output,
            summary=session.summary,
            tags=session.tags,
            created_at=session.created_at,
            device_id=session.device_id,
            updated_at=session.updated_at,
            sync_state=session.sync_state,
        )
