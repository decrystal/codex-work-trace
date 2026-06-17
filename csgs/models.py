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
    device_id: str | None = None
    updated_at: str | None = None
    sync_state: str | None = None


@dataclass(frozen=True)
class Session:
    id: str
    parent_id: str | None
    project: str | None
    title: str | None
    summary: str
    tags: list[str] = field(default_factory=list)
    summary_turn_index: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    device_id: str | None = None
    sync_state: str | None = None


@dataclass(frozen=True)
class Turn:
    id: str
    session_id: str
    turn_index: int
    prompt: str
    output: str
    summary: str
    created_at: str | None = None
