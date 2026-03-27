# ABOUTME: MCP configuration types and YAML config loader.
# ABOUTME: Defines McpTransport enum, McpServerConfig dataclass, and load_mcp_config().

from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import get_dynagent_settings

logger = get_logger(__name__)


class McpTransport(Enum):
    """Supported MCP transport protocols."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


@dataclass
class McpServerConfig:
    """Configuration for connecting to an MCP server."""

    name: str
    transport: McpTransport

    # Stdio transport
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None

    # Streamable HTTP transport
    url: str | None = None

    # Auth — key in Dynagent state["mcp_auth"] dict holding the token
    auth_state_key: str | None = None


def get_config_dir():
    """Get the configuration directory from dynagent settings."""
    return get_dynagent_settings().dynagent_config_root_dir


def load_mcp_config() -> dict[str, dict[str, Any]]:
    """Read mcp_servers section from agents.yaml.

    Returns {} if the section is absent or agents.yaml doesn't exist.
    """
    config_path = get_config_dir() / "agents.yaml"
    try:
        with open(config_path) as f:  # noqa: PTH123
            data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.info("No agents.yaml found at %s — no MCP servers configured", config_path)
        return {}

    result = data.get("mcp_servers", {}) if data else {}
    if result:
        logger.info("Loaded MCP server config for: %s", list(result.keys()))
    return result
