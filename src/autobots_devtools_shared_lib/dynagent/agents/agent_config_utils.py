# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


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
        logger.exception(f"Error reading prompt {name} from {prompt_dir}")
        return f"Error reading prompt: {e}"


def load_schema(name: str) -> dict:
    """Read and parse a JSON schema file by name from the schemas/ directory.

    Args:
        name: Schema filename (e.g., "joke-output.json", "01-preface.json")

    Returns:
        Parsed JSON schema as dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        ValueError: If JSON is invalid
    """
    config_dir = get_config_dir()
    schema_dir = Path(config_dir) / "schemas"
    schema_file = schema_dir / name

    if not schema_file.exists():
        error_msg = f"Schema file not found: {schema_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with Path.open(schema_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in schema {schema_file}: {e}"
        logger.exception(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Error reading schema {name} from {schema_dir}: {e}"
        logger.exception(error_msg)
        raise


def get_agent_list() -> list[str]:
    """Return list of agent names from config."""
    return list(load_agents_config().keys())


def get_prompt_map() -> dict[str, str]:
    """Return {agent_name: prompt_text} loaded from prompt files."""
    return {name: load_prompt(cfg.prompt) for name, cfg in load_agents_config().items()}


def get_schema_path_map() -> dict[str, str | None]:
    """Return {agent_name: raw_schema_path_or_None}."""
    return {name: cfg.output_schema for name, cfg in load_agents_config().items()}


def get_schema_map() -> dict[str, dict | None]:
    """Return {agent_name: parsed_schema_dict_or_None} loaded from schema files.

    Reads all schema files referenced in agents.yaml at startup.
    Agents without output_schema get None.

    Returns:
        Dictionary mapping agent names to parsed schema dicts

    Raises:
        FileNotFoundError: If a referenced schema file is missing
        ValueError: If a schema file contains invalid JSON
    """
    result = {}
    for agent_name, cfg in load_agents_config().items():
        if cfg.output_schema is None:
            result[agent_name] = None
        else:
            logger.info(f"Loading schema '{cfg.output_schema}' for agent '{agent_name}'")
            result[agent_name] = load_schema(cfg.output_schema)

    logger.info(f"Loaded {sum(1 for v in result.values() if v is not None)} schemas")
    return result


def get_tool_map() -> dict[str, list[Any]]:
    """Return {agent_name: [tool_objects]}.

    Resolves each agent's tool list from agents.yaml against the combined
    default + usecase tool pool.

    Raises:
        ValueError: If a tool name referenced in agents.yaml cannot be resolved
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
                error_msg = f"Unresolved tool '{tool_name}' for agent '{name}'. Available tools: {sorted(tool_by_name.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)
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
