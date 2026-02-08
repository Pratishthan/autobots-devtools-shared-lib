# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent loaded from agents.yaml."""

    agent_id: str
    prompt: str
    tools: list[str]
    section: str | None = None
    output_schema: str | None = None
    approach: str | None = None
    dynamic: bool = False
    batch_enabled: bool = False
    is_default: bool = False
    max_concurrency: int | None = None

    @classmethod
    def from_dict(cls, agent_id: str, data: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from a dictionary."""
        return cls(
            agent_id=agent_id,
            prompt=data.get("prompt", ""),
            tools=data.get("tools", []),
            section=data.get("section"),
            output_schema=data.get("output_schema"),
            approach=data.get("approach"),
            dynamic=data.get("dynamic", False),
            batch_enabled=data.get("batch_enabled", False),
            is_default=data.get("is_default", False),
            max_concurrency=data.get("max_concurrency"),
        )


_GLOBAL_AGENT_CONFIG: dict[str, AgentConfig] = {}


def _reset_agent_config() -> None:
    """Clear the cached agent config — for test isolation."""
    global _GLOBAL_AGENT_CONFIG
    _GLOBAL_AGENT_CONFIG = {}


def get_config_dir() -> Path:
    """Get the configuration directory from environment variable."""
    config_dir = os.getenv("DYNAGENT_CONFIG_ROOT_DIR")
    logger.info(f"Using config directory: {config_dir}")
    if not config_dir:
        raise OSError("DYNAGENT_CONFIG_ROOT_DIR environment variable is not set")
    return Path(config_dir)


# NOTE: Call get_config_dir() instead of using a global CONFIG_DIR to allow
# environment variable setup (e.g. in tests) before the path is resolved.


def load_agents_config() -> dict[str, AgentConfig]:
    """Load agent configurations from agents.yaml."""
    global _GLOBAL_AGENT_CONFIG
    if _GLOBAL_AGENT_CONFIG:
        return _GLOBAL_AGENT_CONFIG
    config_dir = get_config_dir()
    config_path = Path(config_dir) / "agents.yaml"

    with open(config_path) as f:  # noqa: PTH123
        data = yaml.safe_load(f)

    agents = {}
    for agent_id, agent_data in data.get("agents", {}).items():
        agents[agent_id] = AgentConfig.from_dict(agent_id, agent_data)

    _GLOBAL_AGENT_CONFIG = agents

    logger.info(f"Loaded {len(_GLOBAL_AGENT_CONFIG)} agent configs from {config_path}")
    return agents


def load_prompt(name: str) -> str:
    """Read a prompt file by name from the prompts/ directory."""
    config_dir = get_config_dir()
    prompt_dir = Path(config_dir) / "prompts"
    try:
        with open(prompt_dir / f"{name}.md") as f:  # noqa: PTH123
            return f.read()
    except Exception as e:
        logger.error(f"Error reading prompt {name} from {prompt_dir}: {e}")
        return f"Error reading prompt: {e}"


def get_agent_list() -> list[str]:
    """Return list of agent names from config."""
    return list(load_agents_config().keys())


def get_prompt_map() -> dict[str, str]:
    """Return {agent_name: prompt_text} loaded from prompt files."""
    return {name: load_prompt(cfg.prompt) for name, cfg in load_agents_config().items()}


def get_schema_path_map() -> dict[str, str | None]:
    """Return {agent_name: raw_schema_path_or_None}."""
    return {name: cfg.output_schema for name, cfg in load_agents_config().items()}


def get_tool_map() -> dict[str, list[Any]]:
    """Return {agent_name: [tool_objects]}.

    Resolves each agent's tool list from agents.yaml against the combined
    default + usecase tool pool.  Unrecognised tool names are skipped with a warning.
    """
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_all_tools

    all_tools = get_all_tools()
    tool_by_name = {t.name: t for t in all_tools}
    result: dict[str, list[Any]] = {}
    for name, cfg in load_agents_config().items():
        resolved: list[Any] = []
        for tool_name in cfg.tools:
            if tool_name in tool_by_name:
                resolved.append(tool_by_name[tool_name])
                logger.info(f"Agent '{name}': adding resolved tool '{tool_name}'")
            else:
                logger.warning(
                    f"get_tool_map: unresolved tool '{tool_name}' for agent '{name}'"
                )
        result[name] = resolved
    return result


def get_batch_enabled_agents() -> list[str]:
    """Return list of agent names that have batch_enabled=True."""
    return [name for name, cfg in load_agents_config().items() if cfg.batch_enabled]


def get_default_agent() -> str | None:
    """Return the name of the default agent, or None if not set."""
    for name, cfg in load_agents_config().items():
        if cfg.is_default:
            return name
    return None
