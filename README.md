# Codex Session Graph System

CSGS is a lightweight local-first recorder for Codex or other LLM coding assistant conversations. It records Codex chats as sessions, stores summary checkpoints as append-only entries, and can sync project history across machines.

This is a thought lineage system, not a workflow engine. `parent_id` means "derived from this session"; it is not an execution dependency. Sync is append-only: same IDs are skipped, new IDs are inserted, and existing records are not rewritten.

## Data Semantics

```text
project = normalized project identity
group   = optional association of related projects
session = one full Codex chat/thread
entry   = one append-only summary checkpoint for a session
turn    = one User prompt -> Assistant output pair inside a session
```

Project IDs are derived from the current directory:

- GitHub remote: `github:owner/repo`
- Other git remote: `host:owner/repo`
- Git root with no remote: `path:/absolute/git/root`
- Non-git folder: `path:/absolute/folder`

`codex_session_id` stores Codex's native session/thread ID when available. MCP tools read MCP request metadata when Codex provides it, but they do not treat the MCP transport session ID as the Codex thread ID. For direct CLI calls from inside a Codex session, CSGS uses `CODEX_THREAD_ID` when `--codex-session-id` is omitted. Treat it as useful metadata, not a required key.

The default recording flow is MCP-first. Ask Codex to use CSGS; the MCP server instructions tell Codex to call `get_runtime_context` and then `record_current_session_summary`. Each call creates a new `entry` and updates `session.summary` as the latest aggregate summary. CSGS does not rebuild a long transcript every time.

## Install

Recommended local install from GitHub source:

```bash
git clone git@github.com:decrystal/codex-work-trace.git
cd codex-work-trace
python -m pip install -e ".[mcp]"
csgs install --mode local
```

Recommended remote install:

```bash
csgs install --mode remote --endpoint https://csgs.example.com --token "$CSGS_TOKEN"
```

Release installer after binary assets are published:

```bash
sh install/install.sh --mode local
```

For local development from this checkout:

```bash
python -m pip install -e ".[dev,mcp]"
python -m csgs.cli install --mode local --runtime dev-python --db .csgs/csgs.sqlite3
```

`csgs install` writes CSGS config and configures the Codex MCP server. It does not install Codex hooks.

Local mode config:

```toml
mode = "local"
db = "/Users/you/.csgs/csgs.sqlite3"
```

Remote mode config:

```toml
mode = "remote"
db = "/Users/you/.csgs/csgs.sqlite3"
endpoint = "https://csgs.example.com"
```

Remote mode configures Codex to call the remote MCP endpoint. The local CLI fallback still writes local SQLite first; after `record-summary`, it automatically push/pulls the current project against the configured remote endpoint.

Codex MCP config for local mode:

```toml
[mcp_servers.csgs]
command = "/path/to/python"
args = ["-m", "csgs.mcp_server"]

[mcp_servers.csgs.env]
CSGS_DB = "/Users/you/.csgs/csgs.sqlite3"
```

Codex MCP config for remote mode:

```toml
[mcp_servers.csgs]
url = "https://csgs.example.com/mcp"

[mcp_servers.csgs.headers]
Authorization = "Bearer your-secret-token"
```

## Codex Plugin

This repository includes two optional Codex plugins and a repo marketplace at `.agents/plugins/marketplace.json`.

- `plugins/csgs-local`: Optional skill helpers for local SQLite.
- `plugins/csgs-remote`: Optional skill helpers for local SQLite plus remote sync.

For local mode:

```bash
csgs install --mode local
codex plugin marketplace add https://github.com/decrystal/codex-work-trace.git
codex plugin add csgs-local@csgs
```

For remote mode:

```bash
csgs install --mode remote --endpoint https://csgs.example.com --token your-secret-token
codex plugin marketplace add https://github.com/decrystal/codex-work-trace.git
codex plugin add csgs-remote@csgs
```

For local development from this checkout:

```bash
/Applications/Codex.app/Contents/Resources/codex plugin marketplace add /Users/decrytal-ade/work/codex-work-trace
/Applications/Codex.app/Contents/Resources/codex plugin add csgs-local@csgs
```

Default local files:

```text
~/.csgs/config.toml
~/.csgs/csgs.sqlite3
```

## How Summary Is Triggered

Ask Codex:

```text
用 CSGS 总结一下这轮对话
```

The CSGS MCP server instructions tell Codex to summarize the visible session in 3-5 sentences and call:

```text
get_runtime_context()
record_current_session_summary(summary="<summary>")
```

The tool returns the entry ID, session ID, Codex session ID when available, project ID, SQLite database path, and runtime context. The CLI command below remains available as a fallback.

## CLI Usage

Record a summary checkpoint for the current Codex session:

```bash
csgs record-summary \
  --summary "Implemented project-first summaries with append-only sync." \
  --cwd "$PWD" \
  --codex-session-id "$CODEX_THREAD_ID"
```

List entries:

```bash
csgs entry-list --project github:decrystal/codex-work-trace
csgs entry-list --session-id S_codex_abc123
```

Associate related projects into a group:

```bash
csgs group-add-project market-research github:decrystal/pindou-market-research --name "Market Research"
csgs group-add-project market-research path:/Users/you/work/local-related-folder
csgs entry-list --group market-research
```

Create a full session with turns:

```bash
csgs --db .csgs/csgs.sqlite3 session-log \
  --id S_001 \
  --project github:owner/repo \
  --codex-session-id codex-session-123 \
  --title "Parser refactor chat" \
  --tags idea,refactor \
  --turn "Refactor the parser|||Changed parser module" \
  --turn "Add search|||Implemented project search"
```

Append a turn:

```bash
csgs --db .csgs/csgs.sqlite3 turn-append S_001 \
  --prompt "Add search" \
  --output "Implemented project search"
```

Trace and search:

```bash
csgs session-trace S_001
csgs session-search --text parser --tags refactor --project github:owner/repo
```

Fork a session:

```bash
csgs session-fork S_001 \
  --id S_002 \
  --codex-session-id codex-session-456 \
  --turn "Try a smaller CLI shape|||Added a CLI sketch"
```

## MCP And HTTP

MCP is the default Codex integration. Use the CLI when you want a direct shell fallback or scripted access.

Local stdio MCP:

```bash
csgs mcp-server
```

Local Streamable HTTP server:

```bash
csgs --db .csgs/csgs.sqlite3 serve \
  --host 127.0.0.1 \
  --port 8765 \
  --transport streamable-http
```

This exposes:

- `http://127.0.0.1:8765/mcp` for Streamable HTTP MCP clients.
- `http://127.0.0.1:8765/api/*` for plain JSON API clients.

The default host is local-only. Do not expose this daemon publicly without adding authentication.

## Docker Deploy

Local Docker server with SQLite persisted in a named volume:

```bash
docker compose up -d --build
curl http://127.0.0.1:8765/health
```

This starts CSGS at:

```text
http://127.0.0.1:8765/mcp
```

HTTPS domain deployment with Caddy:

```bash
CSGS_DOMAIN=csgs.example.com CSGS_TOKEN=your-secret-token \
  docker compose -f compose.yaml -f compose.caddy.yaml up -d --build
```

Then configure Codex remote MCP:

```bash
csgs install --mode remote --endpoint https://csgs.example.com --token your-secret-token
```

Docker files:

```text
Dockerfile
compose.yaml
compose.caddy.yaml
deploy/caddy/Caddyfile
```

The Docker image stores SQLite at `/data/csgs.sqlite3`. The default compose file binds the service to host `127.0.0.1` only. The Caddy overlay publishes ports `80` and `443`; set `CSGS_TOKEN` before exposing it.

When `CSGS_TOKEN` is set, `/ui`, `/mcp`, and `/api/*` require a bearer token. `/health` stays open for health checks. Open the query UI with:

```text
https://csgs.example.com/ui?token=your-secret-token
```

The UI stores the token in browser local storage and sends it as:

```http
Authorization: Bearer your-secret-token
```

Key MCP tools:

```text
get_runtime_context()
record_current_session_summary(summary, codex_session_id?, cwd?, project_id?)
record_summary(summary, project_id?, cwd?, codex_session_id?)
list_project_entries(project_id)
list_group_entries(group_id)
search_sessions(text?, tags?, project?)
trace_session(id)
```

HTTP examples:

```bash
curl -s http://127.0.0.1:8765/api/entries \
  -H 'Content-Type: application/json' \
  -d '{
    "summary": "Recorded the current Codex session.",
    "cwd": "/path/to/project",
    "codexSessionId": "codex-session-123"
  }'

curl -s 'http://127.0.0.1:8765/api/entries?project=github:owner/repo'
curl -s 'http://127.0.0.1:8765/api/sync/export?project=github:owner/repo'
curl -s http://127.0.0.1:8765/api/sync/import \
  -H 'Content-Type: application/json' \
  -d @project-sync.json
```

Import skips existing session, turn, and entry IDs.

## Python API

```python
from csgs.service import SessionGraphService
from csgs.store import CSGSStore

service = SessionGraphService(CSGSStore(".csgs/csgs.sqlite3"))
entry = service.record_summary(
    summary="Implemented project-first summaries.",
    cwd=".",
    codex_session_id="codex-session-123",
)
print(entry.id, entry.project_id, entry.session_id)
```

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    project TEXT,
    codex_session_id TEXT,
    title TEXT,
    summary TEXT,
    tags TEXT,
    summary_turn_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_id TEXT,
    sync_state TEXT DEFAULT 'local'
);

CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    device_id TEXT,
    kind TEXT DEFAULT 'summary',
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_state TEXT DEFAULT 'local'
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS group_projects (
    group_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, project_id)
);

CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    codex_session_id TEXT,
    codex_turn_id TEXT,
    turn_index INTEGER NOT NULL,
    prompt TEXT,
    output TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, turn_index)
);
```
