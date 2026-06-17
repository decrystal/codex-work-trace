# Codex Session Graph System

CSGS is a lightweight local-first recorder for Codex or other LLM coding assistant conversations. Each conversation turn can be stored as a run node with prompt, output, summary, tags, project, and an optional `parent_id` origin link.

This is a thought lineage system, not a workflow engine. `parent_id` means "derived from this run"; it is not an execution dependency.

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

Create a run:

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

There is no separate `summary` tool in the MVP. Summary is generated inside:

- `log_run(prompt, output, parent_id?, project?, tags?, run_id?)`
- `fork_run(id, prompt?, output?, project?, tags?, run_id?)`

So in a Codex conversation, the trigger is simply: call the CSGS MCP `log_run` tool after the assistant has produced a meaningful result. CSGS generates the summary and writes the SQLite row in the same operation.

For manual use, ask Codex:

```text
Record this turn in CSGS with project=csgs and tags=idea.
```

For lower-friction use, add a persistent instruction such as:

```text
When a task is complete, call the csgs MCP log_run tool with the user's request as prompt, your final result as output, and any known parent_id. Do not call a separate summary tool; CSGS generates summary automatically.
```

For fully automatic end-of-turn recording, use a Codex lifecycle hook that forwards prompt/output to this logger. This repository exposes the MCP tools and CLI needed by that hook, but does not ship a hook implementation in the MVP.

## Hook-Friendly HTTP API

Hooks and scripts can call plain JSON endpoints without implementing the MCP protocol.

Log a run:

```bash
curl -s http://127.0.0.1:8765/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "A_001",
    "project": "demo",
    "prompt": "Refactor the parser",
    "output": "Changed parser module",
    "tags": ["refactor"]
  }'
```

Trace a run:

```bash
curl -s http://127.0.0.1:8765/api/runs/A_001/trace
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
root = service.log_run("Start idea", "Created initial implementation.", run_id="A_001")
branch = service.fork_run(root.id, "Try variant", "Created branch.", run_id="B_002")
print(service.trace_run(branch.id))
```

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    project TEXT,
    prompt TEXT,
    output TEXT,
    summary TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_id TEXT,
    updated_at TIMESTAMP,
    sync_state TEXT DEFAULT 'local'
);
```
