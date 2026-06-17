from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Run:
    id: str
    parent_id: str | None
    project: str | None
    prompt: str
    output: str
    summary: str
    tags: list[str] = field(default_factory=list)
    created_at: str | None = None
