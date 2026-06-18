from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB = Path(".csgs/csgs.sqlite3")


@dataclass(frozen=True)
class CSGSConfig:
    mode: str = "local"
    db: Path | None = None
    endpoint: str | None = None
    token: str | None = None


def csgs_home() -> Path:
    return Path(os.environ.get("CSGS_HOME", Path.home() / ".csgs")).expanduser()


def default_config_path() -> Path:
    return csgs_home() / "config.toml"


def default_local_db_path() -> Path:
    return csgs_home() / "csgs.sqlite3"


def load_config(path: str | Path | None = None) -> CSGSConfig:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if not config_path.exists():
        return CSGSConfig()

    data = tomllib.loads(config_path.read_text())
    mode = str(data.get("mode", "local"))
    db_value = data.get("db")
    endpoint_value = data.get("endpoint")
    token_value = data.get("token")

    return CSGSConfig(
        mode=mode,
        db=Path(str(db_value)).expanduser() if db_value else None,
        endpoint=str(endpoint_value).rstrip("/") if endpoint_value else None,
        token=str(token_value) if token_value else None,
    )


def write_config(
    *,
    mode: str,
    db_path: str | Path | None = None,
    endpoint: str | None = None,
    token: str | None = None,
    path: str | Path | None = None,
) -> Path:
    if mode not in {"local", "remote"}:
        raise ValueError("mode must be one of: local, remote")
    if mode == "remote" and not endpoint:
        raise ValueError("--endpoint is required for remote mode")

    config_path = Path(path).expanduser() if path is not None else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f'mode = "{mode}"']
    db = Path(db_path).expanduser() if db_path is not None else default_local_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    lines.append(f'db = "{_toml_string(str(db))}"')
    if mode == "remote":
        lines.append(f'endpoint = "{_toml_string(endpoint.rstrip("/"))}"')
        if token:
            lines.append(f'token = "{_toml_string(token)}"')

    config_path.write_text("\n".join(lines) + "\n")
    return config_path


def resolve_db_path(value: str | Path | None = None) -> Path:
    if value:
        return Path(value).expanduser()
    env_db = os.environ.get("CSGS_DB")
    if env_db:
        return Path(env_db).expanduser()
    config = load_config()
    if config.db is not None:
        return config.db
    return DEFAULT_DB


def mcp_endpoint(endpoint: str) -> str:
    stripped = endpoint.rstrip("/")
    return stripped if stripped.endswith("/mcp") else f"{stripped}/mcp"


def api_base(endpoint: str) -> str:
    stripped = endpoint.rstrip("/")
    return stripped.removesuffix("/mcp")


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
