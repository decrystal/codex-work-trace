# CSGS Local HTTP and Sync Design

## Goal

Evolve CSGS from a stdio-oriented MVP into a local-first daemon. The default interaction model is an HTTP MCP server backed by local SQLite. When users need synchronization, CSGS exports or imports project-scoped run data so a separate central sync service can be added later.

## Approved Architecture

The local process owns the SQLite database and exposes two HTTP surfaces on the same host and port:

- `/mcp`: Streamable HTTP MCP endpoint for Codex and other MCP clients.
- `/api/*`: plain JSON endpoints for hooks, scripts, smoke tests, and future sync tooling.

SQLite remains the local source of truth. Network availability must not affect `log_run`, `fork_run`, `trace_run`, or search.

## Components

- `csgs/mcp_server.py`: builds the FastMCP server, registers MCP tools, and attaches custom JSON API routes.
- `csgs/http_api.py`: JSON request parsing, response formatting, hook-friendly run logging endpoints, search, trace, and sync export/import handlers.
- `csgs/sync.py`: project-scoped export/import payload helpers.
- `csgs/store.py`: additive schema migration and project-scoped listing.
- `csgs/service.py`: import/export-facing helpers while preserving existing run semantics.

## HTTP API

The daemon exposes:

- `GET /health`: returns daemon status and database path.
- `POST /api/runs`: logs a run and automatically generates summary.
- `GET /api/runs/{id}`: returns a run.
- `POST /api/runs/{id}/fork`: forks a run.
- `GET /api/runs/{id}/trace`: returns trace text.
- `GET /api/search?project=&text=&tags=`: returns matching runs.
- `GET /api/sync/export?project=`: returns a project-scoped append-only payload.
- `POST /api/sync/import`: imports runs from a payload, skipping rows already present.

## Data Model Extension

The existing table stays compatible. New columns are added by migration:

```sql
ALTER TABLE runs ADD COLUMN device_id TEXT;
ALTER TABLE runs ADD COLUMN updated_at TIMESTAMP;
ALTER TABLE runs ADD COLUMN sync_state TEXT DEFAULT 'local';
```

`id` remains the true primary key. Existing `A_001` style IDs are still accepted. New generated IDs remain globally unlikely to collide because they use UUID-derived values.

## Sync Model

The MVP sync model is append-only:

- Export returns runs for one project, ordered by `created_at` and `id`.
- Import inserts missing runs and skips IDs already present.
- Existing runs are not overwritten.
- Central service, authentication, conflict resolution, and deletion propagation are out of scope.

This is enough to sync local project slices without making normal logging dependent on central infrastructure.

## Security

The default daemon host is `127.0.0.1` and default port is `8765`. The JSON API has no authentication in this local MVP and should not be exposed publicly. Remote sync or public HTTP deployment requires a later auth layer.

## Testing

Tests must cover:

- Schema migration adds sync metadata without breaking old run operations.
- Project export returns only the requested project.
- Import skips duplicate IDs.
- JSON API can log, get, fork, trace, search, and export runs.
- FastMCP app includes custom API routes and can be constructed.
