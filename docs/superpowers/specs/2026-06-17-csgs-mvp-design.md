# CSGS MVP Design

## Goal

Codex Session Graph System (CSGS) is a lightweight local-first recorder for LLM coding assistant conversations. It stores each conversation as a run node, generates a short summary, supports origin links through `parent_id`, and exposes local CLI and MCP entry points.

## Scope

The MVP implements run creation, automatic mock summary generation, fork, trace, search, SQLite persistence, and MCP tool stubs. It does not implement workflow execution, dependency scheduling, rollback, replay, diffing, or UI.

## Architecture

The implementation is a small Python package with no runtime dependency beyond the standard library for core behavior. SQLite is accessed through a focused store module, business operations live in a service module, summary generation is isolated behind a simple function, and adapters expose the service through CLI and MCP-style functions.

The graph relationship is intentionally weak: `parent_id` means "origin reference" only. It is not a dependency edge and no command will execute or replay parent runs.

## Data Model

SQLite table:

```sql
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
```

`tags` is stored as a comma-separated string for MVP simplicity. Search supports `prompt`, `summary`, `tags`, and `project`.

## Components

- `csgs/store.py`: database connection, schema initialization, CRUD, search, children lookup.
- `csgs/summary.py`: deterministic mock summary generator with a 3 to 5 sentence upper bound.
- `csgs/service.py`: high-level operations: `log_run`, `get_run`, `fork_run`, `trace_run`, `search_runs`.
- `csgs/cli.py`: command line commands: `init`, `log`, `get`, `fork`, `trace`, `search`.
- `csgs/mcp_server.py`: MCP tool stub functions with the same semantics as the service methods.
- `tests/`: pytest coverage for storage, service, trace rendering, search, and MCP stubs.

## MCP Behavior

The MCP server exposes `log_run(prompt, output, parent_id=None, project=None, tags=None)`, `get_run(id)`, `trace_run(id)`, and `fork_run(id, prompt=None, output=None)`.

Summary generation is triggered inside `log_run` and `fork_run`. In normal use, Codex should call `log_run` after a meaningful assistant turn; users do not need to call a separate summary tool. Fully automatic end-of-turn recording in Codex is best handled by a Codex hook or durable instruction that calls the MCP tool.

## Error Handling

- Missing parent run raises a clear `RunNotFoundError`.
- Duplicate run IDs raise a clear `RunAlreadyExistsError`.
- Missing target run for `get`, `trace`, or `fork` raises `RunNotFoundError`.
- Database directories are created automatically when possible.

## Testing

Implementation follows TDD. Tests cover:

- Schema creation and run persistence.
- Automatic summary generation during logging.
- Forked run parent linkage.
- Trace output for ancestors and descendants.
- Search by text, tags, and project.
- MCP stub function behavior.

## Assumptions

- Python is the implementation language.
- The first summary generator is a deterministic mock, not a real LLM call.
- IDs can be generated locally when not supplied.
- Local-first storage uses a configurable SQLite path, defaulting to `.csgs/csgs.sqlite3`.
