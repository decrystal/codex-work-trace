---
name: csgs-install
description: Install or verify CSGS Remote MCP-first integration for on-demand Codex session summaries with remote sync.
---

# CSGS Remote Install

Use this skill when the user wants to install, verify, or debug remote CSGS integration.

## Workflow

1. Check whether `csgs` is available:

   ```bash
   command -v csgs
   csgs --help
   ```

2. Configure remote mode:

   ```bash
   csgs install --mode remote --endpoint https://csgs.example.com
   ```

3. Confirm local config:

   ```text
   ~/.csgs/config.toml
   ```

Remote mode configures Codex to call the remote MCP endpoint. The CLI fallback still writes local SQLite first, then automatically push/pulls the current project against the configured remote endpoint.

Do not ask the user to trust hooks for the default flow. CSGS Remote records only when the user asks for a summary.

## Output

Report whether the executable, Codex MCP config, endpoint config, and local cache path are ready.
