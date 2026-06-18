---
name: csgs-install
description: Install or verify CSGS Local MCP-first integration for on-demand Codex session summaries with local SQLite.
---

# CSGS Local Install

Use this skill when the user wants to install, verify, or debug local CSGS integration.

## Workflow

1. Check whether `csgs` is available:

   ```bash
   command -v csgs
   csgs --help
   ```

2. If `csgs` is missing, recommend installing from source:

   ```bash
   git clone git@github.com:decrystal/codex-work-trace.git
   cd codex-work-trace
   python -m pip install -e ".[mcp]"
   ```

3. Verify local mode:

   ```bash
   csgs install --mode local
   ```

4. Confirm the default config and database:

   ```text
   ~/.csgs/config.toml
   ~/.csgs/csgs.sqlite3
   ```

Do not ask the user to trust hooks for the default flow. `csgs install --mode local` configures the Codex MCP server; summaries are still recorded only when the user asks for a summary.

## Output

Report whether the executable, Codex MCP config, local config, and database path are ready.
