from __future__ import annotations

import os
from collections.abc import Mapping


def current_codex_session_id(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    return _non_blank(env.get("CODEX_THREAD_ID")) or _non_blank(env.get("CODEX_SESSION_ID"))


def _non_blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
