"""Configuration for the Node-RED instance manager server, loaded from a YAML file."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


@dataclass
class TemplateConfig:
    """Configuration for a single Node-RED environment/template."""

    name: str
    path: Path
    min_port: int
    max_port: int


def _load_yaml_config(
    config_file: Path,
) -> tuple[str, str, str, int, dict[str, TemplateConfig]]:
    """
    Load node-red-config.yaml and return
    (node_red_executable, base_path, manager_host, manager_port, environments_by_name).

    Expected YAML structure::

        node_red_executable: /usr/local/bin/node-red  # optional, defaults to "node-red"

        # Root directory prepended to all workspace paths when resolving flows.json.
        base_path: /data/workspaces

        # Host and port for the manager server itself and for building instance URLs.
        node_red_manager_server_host: 0.0.0.0   # optional, defaults to "0.0.0.0"
        node_red_manager_server_port: 9003       # optional, defaults to 9003

        environments:
          - name: compose-engine-template
            path: /path/to/compose-engine-template
            min_port: 1880
            max_port: 1920

          - name: basic-template
            path: /path/to/basic-template
            min_port: 1921
            max_port: 1980
    """
    if not config_file.exists():
        raise FileNotFoundError(
            f"Node-RED config file not found: {config_file}. "
            "Set NODE_RED_CONFIG_FILE env var to point to your node-red-config.yaml."
        )

    with config_file.open() as f:
        data = yaml.safe_load(f) or {}

    node_red_executable: str = data.get("node_red_executable", "node-red") or "node-red"
    base_path: str = data.get("base_path", "") or ""
    manager_host: str = (
        data.get("node_red_manager_server_host", "0.0.0.0") or "0.0.0.0"  # noqa: S104
    )
    manager_port: int = int(data.get("node_red_manager_server_port", 9003))

    raw_environments: list[dict] = data.get("environments") or []
    environments: dict[str, TemplateConfig] = {}
    for entry in raw_environments:
        name = str(entry.get("name", "")).strip()
        raw_path = str(entry.get("path", "")).strip()
        min_port = int(entry.get("min_port", 1880))
        max_port = int(entry.get("max_port", 1980))
        if not name:
            raise ValueError("Each environment entry must have a non-empty 'name' field.")
        if not raw_path:
            raise ValueError(f"Environment '{name}' is missing the 'path' field.")
        environments[name] = TemplateConfig(
            name=name,
            path=Path(raw_path).resolve(),
            min_port=min_port,
            max_port=max_port,
        )

    return node_red_executable, base_path, manager_host, manager_port, environments


# Resolve config file path from env var; default to node-red-config.yaml in cwd.
_config_file = Path(os.getenv("NODE_RED_CONFIG_FILE", "node-red-config.yaml"))

# Load at module import time so config is available immediately.
# If the file is absent the server will fail fast during lifespan startup (validate() call).
try:
    _node_red_executable, _base_path, _manager_host, _manager_port, _environments = (
        _load_yaml_config(_config_file)
    )
except FileNotFoundError:
    _node_red_executable = "node-red"
    _base_path = ""
    _manager_host = "0.0.0.0"  # noqa: S104
    _manager_port = 9003
    _environments = {}


class NodeRedServerConfig:
    """Configuration for the Node-RED instance manager server."""

    # All settings loaded from YAML
    node_red_executable: str = _node_red_executable
    base_path: str = _base_path
    node_red_manager_server_host: str = _manager_host
    node_red_manager_server_port: int = _manager_port
    environments: dict[str, TemplateConfig] = _environments

    @classmethod
    def validate(cls) -> None:
        """Fail fast on startup if configuration is unusable."""
        if not _config_file.exists():
            raise ValueError(
                f"Node-RED config file not found: {_config_file}. "
                "Set NODE_RED_CONFIG_FILE env var to point to your node-red-config.yaml."
            )

        if not cls.base_path:
            raise ValueError(
                "base_path is required in node-red-config.yaml. "
                "Set it to the root directory for workspace paths."
            )

        if not cls.environments:
            raise ValueError(
                "No environments defined in node-red-config.yaml. "
                "Add at least one entry under 'environments:'."
            )

        for name, tmpl in cls.environments.items():
            if tmpl.min_port >= tmpl.max_port:
                raise ValueError(
                    f"Environment '{name}': min_port ({tmpl.min_port}) must be less than "
                    f"max_port ({tmpl.max_port})."
                )
            if not tmpl.path.exists():
                raise ValueError(f"Environment '{name}' path does not exist: {tmpl.path}")
            if not (tmpl.path / "settings.js").exists():
                raise ValueError(f"Environment '{name}' is missing settings.js at: {tmpl.path}")
