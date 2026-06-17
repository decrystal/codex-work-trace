# CSGS Session and Turn Design

## Goal

Correct CSGS semantics so one graph node represents a full Codex chat/session, while individual user/assistant exchanges are stored as turns inside that session.

## Semantics

- Session: a complete Codex chat/thread and the node used in the session graph.
- Turn: one `User prompt -> Assistant output` pair inside a session.
- `parent_id`: origin reference between sessions, not turn dependency and not execution dependency.
- Session summary: compact summary of the whole session up to `summary_turn_index`.
- Turn summary: compact summary of one turn.

## Incremental Summary

`append_turn(session_id, prompt, output)` must not rebuild the session summary from the full transcript. It creates a summary for the new turn, then updates the session summary from:

- previous `session.summary`
- new `turn.summary`

After the update, `session.summary_turn_index` equals the newest appended turn index. This makes append practical for long chats and keeps token usage bounded.

## Schema

New tables:

```sql
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
```

The existing `runs` table remains as a compatibility layer for older data and APIs. New session-first APIs use `sessions` and `turns`.

## API

Service methods:

- `log_session(project, turns, parent_id=None, tags=None, session_id=None, title=None) -> Session`
- `append_turn(session_id, prompt, output) -> Turn`
- `get_session(session_id) -> Session`
- `list_turns(session_id) -> list[Turn]`
- `trace_session(session_id) -> str`
- `fork_session(source_id, title=None, turns=None, ...) -> Session`

Compatibility methods:

- `log_run(prompt, output, ...)` creates a one-turn session.
- `get_run`, `fork_run`, and `trace_run` map to session behavior where practical.

HTTP endpoints:

- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `GET /api/sessions/{id}/turns`
- `POST /api/sessions/{id}/turns`
- `GET /api/sessions/{id}/trace`

MCP tools mirror the session-first methods and keep old run tools for compatibility.

## Sync

Project export/import moves sessions plus their turns. Import is append-only:

- existing session IDs are skipped
- existing turn IDs are skipped
- no overwrite or conflict resolution in this MVP
