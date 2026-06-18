# CSGS Remote Codex Plugin

This plugin packages remote CSGS integration for Codex:

- skills for install/debug and manual session summaries
- MCP-first recording through `record_current_session_summary`
- CLI fallback through `csgs record-summary`
- local SQLite cache plus automatic project sync when remote mode is configured

It does not install lifecycle hooks. `csgs install --mode remote --endpoint ...` configures the remote Codex MCP server.

The remote endpoint is configured outside the plugin:

```bash
git clone git@github.com:decrystal/codex-work-trace.git
cd codex-work-trace
python -m pip install -e ".[mcp]"
csgs install --mode remote --endpoint https://csgs.example.com
codex plugin marketplace add https://github.com/decrystal/codex-work-trace.git
codex plugin add csgs-remote@csgs
```

Local files:

```text
~/.csgs/config.toml
~/.csgs/csgs.sqlite3
```

To record and sync the current chat, ask Codex:

```text
用 CSGS 总结一下这轮对话
```
