---
name: csgs
description: Record, summarize, search, trace, or sync Codex Session Graph System (CSGS) sessions. Use when the user says "CSGS", "用 CSGS 总结", asks to record the current Codex session, asks for CSGS history, or asks to query CSGS summaries with remote sync.
---

# CSGS Remote

When the user asks to record or summarize the current Codex session, prefer the CSGS MCP tools when they are available:

1. Call `get_runtime_context`.
2. Write a concise 3-5 sentence summary of the visible session.
3. Call `record_current_session_summary(summary="<summary>")`.
4. If remote mode is configured, the server endpoint handles central storage; CLI fallback can also auto-sync.
5. Return the entry id, session id, Codex session id if available, project id, endpoint or SQLite database path, and sync status if present.

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

4. If remote mode is configured, the CLI automatically push/pulls the current project.
5. Return the entry id, session id, Codex session id, project id, endpoint or SQLite database path, and sync status if present.

Use the CLI for lookups:

```bash
csgs entry-list --project <project_id>
csgs entry-list --group <group_id>
csgs session-search --text <text>
csgs session-trace <session_id>
```

Do not use hooks for the default workflow.
