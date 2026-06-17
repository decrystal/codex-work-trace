# Codex Session Graph System

CSGS is a lightweight local-first recorder for Codex or other LLM coding assistant conversations. Each Codex chat/thread is stored as a session graph node, and each user/assistant exchange inside it is stored as a turn.

This is a thought lineage system, not a workflow engine. `parent_id` means "derived from this run"; it is not an execution dependency.

## Data Semantics

```text
session = one full Codex chat/thread, used as the graph node
turn    = one User prompt -> Assistant output pair inside a session
```

Session summaries are incremental. When you append a turn, CSGS summarizes the new turn and updates the session summary from:

```text
previous session summary + new turn summary
```

It does not rebuild the summary from the full transcript, which keeps append cheap for long chats. `summary_turn_index` records the last turn included in the session summary.

## Install

For local development:

```bash
python -m pip install -e ".[dev]"
```

For the default local HTTP MCP daemon:

```bash
python -m pip install -e ".[dev,server]"
```

The core CLI and SQLite library use only the Python standard library at runtime. The `mcp` package is optional and needed when running the HTTP or stdio MCP server.

## Local HTTP Daemon

Start the local-first daemon:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 serve \
  --host 127.0.0.1 \
  --port 8765 \
  --transport streamable-http
```

This exposes:

- `http://127.0.0.1:8765/mcp` for Streamable HTTP MCP clients.
- `http://127.0.0.1:8765/api/*` for hooks and scripts.

The default host is local-only. Do not expose this daemon publicly without adding authentication.

## CLI Usage

Create a full session:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 session-log \
  --id S_001 \
  --project demo \
  --title "Parser refactor chat" \
  --tags idea,refactor \
  --turn "Refactor the parser|||Changed parser module" \
  --turn "Add search|||Implemented project search"
```

Append a new turn:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 turn-append S_001 \
  --prompt "Add MCP setup" \
  --output "Registered the local HTTP MCP server"
```

Trace session lineage:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 session-trace S_001
```

Legacy single-turn run command:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 log \
  --id A_001 \
  --project demo \
  --tags idea,refactor \
  --prompt "Refactor the parser" \
  --output "Changed parser module"
```

Fork a run:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 fork A_001 \
  --id B_002 \
  --prompt "Try a smaller CLI shape" \
  --output "Added a CLI sketch"
```

Trace lineage:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 trace B_002
```

Search:

```bash
python -m csgs.cli --db .csgs/csgs.sqlite3 search --text parser --tags refactor --project demo
```

## Codex MCP Setup

After installing server support and starting the daemon, add this to Codex config:

```toml
[mcp_servers.csgs]
url = "http://127.0.0.1:8765/mcp"
```

For stdio MCP instead of the local daemon:

```bash
codex mcp add csgs --env CSGS_DB=/Users/decrytal-ade/work/codex-work-trace/.csgs/csgs.sqlite3 -- python -m csgs.mcp_server
```

Then use `/mcp` in Codex to inspect active MCP servers.

## How Summary Is Triggered

There is no separate `summary` tool. Summary is generated inside:

- `log_session(project, turns, parent_id?, tags?, session_id?, title?)`
- `append_turn(session_id, prompt, output)`
- legacy `log_run(prompt, output, ...)`, which creates a one-turn session

For a whole Codex chat, call `log_session` with all known turns. For a running chat, call `append_turn` after each new user/assistant pair. `append_turn` updates the session summary from the existing session summary plus the new turn summary.

For manual use, ask Codex:

```text
Record this Codex session in CSGS with project=csgs and tags=idea.
```

For lower-friction use, add a persistent instruction such as:

```text
When a task is complete, call the csgs MCP append_turn tool for the current session with the latest user prompt and assistant output. If no session exists yet, call log_session first. Do not rebuild the full transcript summary; CSGS updates the session summary incrementally.
```

For fully automatic end-of-turn recording, use a Codex lifecycle hook that forwards prompt/output to this logger. This repository exposes the MCP tools and CLI needed by that hook, but does not ship a hook implementation in the MVP.

## Hook-Friendly HTTP API

Hooks and scripts can call plain JSON endpoints without implementing the MCP protocol.

Log a session:

```bash
curl -s http://127.0.0.1:8765/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "S_001",
    "project": "demo",
    "title": "Parser refactor chat",
    "tags": ["refactor"],
    "turns": [
      {
        "prompt": "Refactor the parser",
        "output": "Changed parser module"
      }
    ]
  }'
```

Append a turn:

```bash
curl -s http://127.0.0.1:8765/api/sessions/S_001/turns \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Add search",
    "output": "Implemented project search"
  }'
```

Trace a session:

```bash
curl -s http://127.0.0.1:8765/api/sessions/S_001/trace
```

Export one project for sync:

```bash
curl -s 'http://127.0.0.1:8765/api/sync/export?project=demo'
```

Import an append-only sync payload:

```bash
curl -s http://127.0.0.1:8765/api/sync/import \
  -H 'Content-Type: application/json' \
  -d @project-sync.json
```

Import skips existing run IDs and only inserts missing runs.

## Python API

```python
from csgs.service import SessionGraphService
from csgs.store import RunStore

service = SessionGraphService(RunStore(".csgs/csgs.sqlite3"))
session = service.log_session(
    project="demo",
    title="CSGS chat",
    turns=[{"prompt": "Start idea", "output": "Created initial implementation."}],
    session_id="S_001",
)
service.append_turn(session.id, "Try variant", "Created branch.")
print(service.trace_session(session.id))
```

## SQLite Schema

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
    updated_at TIMESTAMP,
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
