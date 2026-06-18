from __future__ import annotations

import os
import sys
from pathlib import Path
from shutil import which

from csgs.config import mcp_endpoint, write_config


Runtime = str


def install_local(
    *,
    codex_home: str | Path | None = None,
    db_path: str | Path,
    runtime: Runtime = "auto",
    binary_path: str | Path | None = None,
    python_executable: str | None = None,
    source_root: str | Path | None = None,
) -> dict[str, str]:
    db = Path(db_path).expanduser()
    resolved_runtime, resolved_binary = _resolve_runtime(runtime, binary_path)

    csgs_config_path = write_config(mode="local", db_path=db)
    codex_config_path = _codex_config_path(codex_home)
    _upsert_local_mcp_config(
        codex_config_path,
        db_path=db,
        runtime=resolved_runtime,
        binary_path=resolved_binary,
        python_executable=python_executable or sys.executable,
    )

    return {
        "codex_config_path": str(codex_config_path),
        "csgs_config_path": str(csgs_config_path),
        "db_path": str(db),
        "mcp_configured": "true",
        "mode": "local",
        "runtime": resolved_runtime,
        "binary_path": str(resolved_binary) if resolved_binary is not None else "",
    }


def install_remote(
    *,
    endpoint: str,
    token: str | None = None,
    codex_home: str | Path | None = None,
    runtime: Runtime = "auto",
    binary_path: str | Path | None = None,
    python_executable: str | None = None,
    source_root: str | Path | None = None,
) -> dict[str, str]:
    resolved_runtime, resolved_binary = _resolve_runtime(runtime, binary_path)

    csgs_config_path = write_config(mode="remote", endpoint=endpoint, token=token)
    codex_config_path = _codex_config_path(codex_home)
    endpoint_url = mcp_endpoint(endpoint)
    _upsert_remote_mcp_config(codex_config_path, endpoint=endpoint, token=token)

    return {
        "codex_config_path": str(codex_config_path),
        "csgs_config_path": str(csgs_config_path),
        "endpoint": endpoint.rstrip("/"),
        "mcp_endpoint": endpoint_url,
        "mcp_configured": "true",
        "mode": "remote",
        "runtime": resolved_runtime,
        "binary_path": str(resolved_binary) if resolved_binary is not None else "",
        "token_configured": "true" if token else "",
    }


def _resolve_runtime(runtime: Runtime, binary_path: str | Path | None) -> tuple[str, Path | None]:
    if runtime not in {"auto", "binary", "dev-python"}:
        raise ValueError("runtime must be one of: auto, binary, dev-python")
    if runtime == "dev-python":
        return "dev-python", None

    candidate = Path(binary_path).expanduser() if binary_path is not None else None
    if candidate is None:
        found = which("csgs")
        candidate = Path(found).expanduser() if found else None
    if candidate is not None:
        return "binary", candidate
    if runtime == "binary":
        raise ValueError("binary runtime requires --bin or a csgs executable on PATH")
    return "dev-python", None


def _codex_config_path(codex_home: str | Path | None) -> Path:
    home = Path(codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home / "config.toml"


def _upsert_local_mcp_config(
    path: Path,
    *,
    db_path: Path,
    runtime: str,
    binary_path: Path | None,
    python_executable: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stripped = _remove_toml_table_family(path.read_text() if path.exists() else "", "mcp_servers.csgs").rstrip()
    if runtime == "binary":
        if binary_path is None:
            raise ValueError("binary_path is required for binary runtime")
        block = f"""
[mcp_servers.csgs]
command = "{_toml_string(str(binary_path))}"
args = ["mcp-server"]

[mcp_servers.csgs.env]
CSGS_DB = "{_toml_string(str(db_path))}"
""".strip()
    else:
        block = f"""
[mcp_servers.csgs]
command = "{_toml_string(python_executable)}"
args = ["-m", "csgs.mcp_server"]

[mcp_servers.csgs.env]
CSGS_DB = "{_toml_string(str(db_path))}"
""".strip()
    path.write_text(f"{stripped}\n\n{block}\n" if stripped else f"{block}\n")


def _upsert_remote_mcp_config(path: Path, *, endpoint: str, token: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stripped = _remove_toml_table_family(path.read_text() if path.exists() else "", "mcp_servers.csgs").rstrip()
    block = f"""
[mcp_servers.csgs]
url = "{_toml_string(mcp_endpoint(endpoint))}"
""".strip()
    if token:
        block = f"""{block}

[mcp_servers.csgs.headers]
Authorization = "Bearer {_toml_string(token)}"
""".strip()
    path.write_text(f"{stripped}\n\n{block}\n" if stripped else f"{block}\n")


def _remove_toml_table_family(text: str, table: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False
    prefix = f"{table}."
    for line in lines:
        header = _toml_header(line)
        if header is not None:
            skipping = header == table or header.startswith(prefix)
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def _toml_header(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    return stripped.strip("[]").strip()


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
