---
name: csgs-summary
description: Summarize the current Codex session or selected work and record it through CSGS MCP, with CLI fallback.
---

# CSGS Local Summary

Use this skill when the user asks to record, summarize, search, or trace CSGS sessions.

## Recording Workflow

When the user asks to record or summarize the current Codex session, prefer CSGS MCP tools:

1. Call `get_runtime_context`.
2. Write a concise 3-5 sentence summary of the current visible session.
3. Call `record_current_session_summary(summary="<summary>")`.
4. Return the CSGS entry id, session id, Codex session id if available, project id, and SQLite database path.

If MCP is unavailable, use the CLI fallback:

1. Read the current Codex session id from `CODEX_THREAD_ID`.
2. Identify the project from the current directory. CSGS will derive `project_id` from git remote, git root path, or folder path.
3. Write a concise 3-5 sentence summary of the current visible session.
4. Run:

   ```bash
   csgs record-summary \
     --summary "<summary>" \
     --cwd "$PWD" \
     --codex-session-id "$CODEX_THREAD_ID"
   ```

5. Return the CSGS entry id, session id, codex session id, project id, and SQLite database path if known.

Do not use hooks for the default workflow.

## Query Workflow

Use the CLI for lookups:

```bash
csgs entry-list --project <project_id>
csgs entry-list --group <group_id>
csgs session-search --text <text>
csgs session-trace <session_id>
```
