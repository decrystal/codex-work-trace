# CSGS Local Codex Plugin

This plugin packages local CSGS integration for Codex:

- skills for install/debug and manual session summaries
- MCP-first recording through `record_current_session_summary`
- CLI fallback through `csgs record-summary`
- local SQLite storage at `~/.csgs/csgs.sqlite3`

It does not install lifecycle hooks. `csgs install --mode local` configures the Codex MCP server.

Install:

```bash
git clone git@github.com:decrystal/codex-work-trace.git
cd codex-work-trace
python -m pip install -e ".[mcp]"
csgs install --mode local
codex plugin marketplace add https://github.com/decrystal/codex-work-trace.git
codex plugin add csgs-local@csgs
```

Default local files:

```text
~/.csgs/config.toml
~/.csgs/csgs.sqlite3
```

To record the current chat, ask Codex:

```text
用 CSGS 总结一下这轮对话
```
