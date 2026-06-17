# CSGS Session and Turn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make sessions the graph nodes and store individual user/assistant exchanges as turns with incremental session summary updates.

**Architecture:** Add `Session` and `Turn` models and new SQLite tables while retaining old run APIs as compatibility wrappers. Service methods own incremental summary updates. HTTP, MCP, CLI, and sync shift to session-first APIs.

**Tech Stack:** Python 3.11+, SQLite via `sqlite3`, MCP Python SDK/FastMCP, Starlette test client, pytest.

## Global Constraints

- A graph node is a full session/chat, not a single turn.
- A turn is one `User prompt -> Assistant output` pair inside a session.
- Appending a turn updates session summary from previous summary plus the new turn summary only.
- `summary_turn_index` records how far the session summary has incorporated turns.
- Keep existing run APIs working as compatibility wrappers.
- Sync remains append-only.

---

### Task 1: Session and Turn Storage

**Files:**
- Modify: `csgs/models.py`
- Modify: `csgs/store.py`
- Test: `tests/test_session_store.py`

**Interfaces:**
- `Session`
- `Turn`
- `RunStore.create_session(session: Session) -> Session`
- `RunStore.get_session(session_id: str) -> Session | None`
- `RunStore.create_turn(turn: Turn) -> Turn`
- `RunStore.list_turns(session_id: str) -> list[Turn]`
- `RunStore.next_turn_index(session_id: str) -> int`
- `RunStore.update_session_summary(session_id: str, summary: str, summary_turn_index: int) -> Session`

### Task 2: Session Service and Incremental Summary

**Files:**
- Modify: `csgs/summary.py`
- Modify: `csgs/service.py`
- Test: `tests/test_session_service.py`

**Interfaces:**
- `summarize_session_increment(previous_summary: str, turn_summary: str) -> str`
- `SessionGraphService.log_session(...) -> Session`
- `SessionGraphService.append_turn(...) -> Turn`
- `SessionGraphService.get_session(...) -> Session`
- `SessionGraphService.list_turns(...) -> list[Turn]`
- `SessionGraphService.trace_session(...) -> str`

### Task 3: HTTP and MCP Session APIs

**Files:**
- Modify: `csgs/http_api.py`
- Modify: `csgs/mcp_server.py`
- Test: `tests/test_http_api.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- HTTP: `/api/sessions`, `/api/sessions/{id}`, `/api/sessions/{id}/turns`, `/api/sessions/{id}/trace`
- MCP: `log_session`, `append_turn`, `get_session`, `trace_session`

### Task 4: Sync and CLI Documentation

**Files:**
- Modify: `csgs/sync.py`
- Modify: `csgs/cli.py`
- Modify: `README.md`
- Test: `tests/test_sync.py`
- Test: full suite

**Interfaces:**
- project export/import includes `sessions` and `turns`
- CLI adds `session-log`, `turn-append`, `session-get`, `session-trace`

### Task 5: Verification and Daemon Restart

**Steps:**
- Run `python -m pytest -v`
- Start daemon on `127.0.0.1:8765`
- Verify `/health`
- Verify MCP tool list includes session tools
- Update final status with SQLite path
