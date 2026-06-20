---
name: csgs
description: Record, summarize, search, or trace Codex Session Graph System (CSGS) sessions. Use when the user says "CSGS", "用 CSGS 总结", asks to record the current Codex session, asks for CSGS history, or asks to query CSGS summaries.
---

# CSGS Local

When the user asks to record or summarize the current Codex session, prefer the CSGS MCP tools when they are available:

1. Call `get_runtime_context` when it is responsive and useful.
2. Write a concise 3-5 sentence summary of the visible session.
3. Call `record_current_session_summary(summary="<summary>", cwd="<current project cwd when known>")`. Passing `cwd` is recommended for Windows or remote MCP clients because it skips MCP root probing.
4. Return the entry id, session id, Codex session id if available, project id, and SQLite database path.

If MCP is unavailable, use the CLI fallback:

1. Read the current Codex session id from `CODEX_THREAD_ID`.
2. Write a concise 3-5 sentence summary of the visible session.
3. Run:

   ```bash
   csgs record-summary \
     --summary "<summary>" \
     --cwd "$PWD" \
     --codex-session-id "$CODEX_THREAD_ID"
   ```

4. Return the entry id, session id, Codex session id, project id, and SQLite database path if known.

Use the CLI for lookups:

```bash
csgs entry-list --project <project_id>
csgs entry-list --group <group_id>
csgs session-search --text <text>
csgs session-trace <session_id>
```

Do not use hooks for the default workflow.
