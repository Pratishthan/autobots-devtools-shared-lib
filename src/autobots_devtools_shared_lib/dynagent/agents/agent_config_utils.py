# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path("autobots-agents-bro/configs/vision-agent")

logger = logging.getLogger(__name__)


# --- Inline dataclass (generic; no bro_chat dependency) ---


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
        )


# --- Generic config / prompt readers (no bro_chat dependency) ---


def _load_agents_config(config_dir: Path = CONFIG_DIR) -> dict[str, AgentConfig]:
    """Load agent configurations from agents.yaml."""
    config_path = Path(config_dir) / "agents.yaml"

    with open(config_path) as f:  # noqa: PTH123
        data = yaml.safe_load(f)

    agents = {}
    for agent_id, agent_data in data.get("agents", {}).items():
        agents[agent_id] = AgentConfig.from_dict(agent_id, agent_data)

    logger.info(f"Loaded {len(agents)} agent configs from {config_path}")
    return agents


def _load_prompt(name: str) -> str:
    """Read a prompt file by name from the prompts/ directory."""
    try:
        with open(f"prompts/{name}.md") as f:  # noqa: PTH123
            return f.read()
    except Exception as e:
        logger.error(f"Error reading prompt {name}: {e}")
        return f"Error reading prompt: {e}"


# --- Public accessors (used by AgentMeta) ---


def agent_config_reader(config_dir: Path = CONFIG_DIR) -> dict[str, AgentConfig]:
    """Load raw agent config from YAML."""
    return _load_agents_config(config_dir)


def get_agent_list(config_dir: Path = CONFIG_DIR) -> list[str]:
    """Return list of agent names from config."""
    return list(agent_config_reader(config_dir).keys())


def get_prompt_map(config_dir: Path = CONFIG_DIR) -> dict[str, str]:
    """Return {agent_name: prompt_text} loaded from prompt files."""
    return {
        name: _load_prompt(cfg.prompt)
        for name, cfg in agent_config_reader(config_dir).items()
    }


def get_schema_path_map(config_dir: Path = CONFIG_DIR) -> dict[str, str | None]:
    """Return {agent_name: raw_schema_path_or_None}."""
    return {
        name: cfg.output_schema for name, cfg in agent_config_reader(config_dir).items()
    }


def get_tool_map(config_dir: Path = CONFIG_DIR) -> dict[str, list[Any]]:
    """Return {agent_name: [tool_objects]}.

    Resolves each agent's tool list from agents.yaml against the combined
    default + usecase tool pool.  Unrecognised tool names are skipped with a warning.
    """
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_all_tools

    all_tools = get_all_tools()
    tool_by_name = {t.name: t for t in all_tools}
    result: dict[str, list[Any]] = {}
    for name, cfg in _load_agents_config(config_dir).items():
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
