# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

from pathlib import Path
from typing import Any

from bro_chat.config.section_config import load_agents_config
from bro_chat.models.outputs import (
    EntityOutput,
    FeaturesOutput,
    GettingStartedOutput,
    PrefaceOutput,
)
from bro_chat.utils.files import load_prompt

# Mapping from schema filename to output dataclass
SCHEMA_TO_MODEL: dict[str, Any] = {
    "vision-agent/01-preface.json": PrefaceOutput,
    "vision-agent/02-getting-started.json": GettingStartedOutput,
    "vision-agent/03-01-list-of-features.json": FeaturesOutput,
    "vision-agent/05-entity.json": EntityOutput,
}

CONFIG_DIR = Path("configs/vision-agent")


def agent_config_reader(config_dir: Path = CONFIG_DIR):
    """Load raw agent config from YAML."""
    return load_agents_config(config_dir)


def get_agent_list(config_dir: Path = CONFIG_DIR) -> list[str]:
    """Return list of agent names from config."""
    return list(agent_config_reader(config_dir).keys())


def get_prompt_map(config_dir: Path = CONFIG_DIR) -> dict[str, str]:
    """Return {agent_name: prompt_text} loaded from prompt files."""
    return {
        name: load_prompt(cfg.prompt)
        for name, cfg in agent_config_reader(config_dir).items()
    }


def get_output_map(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    """Return {agent_name: output_dataclass_or_None}."""
    return {
        name: SCHEMA_TO_MODEL.get(cfg.output_schema) if cfg.output_schema else None
        for name, cfg in agent_config_reader(config_dir).items()
    }


def get_schema_path_map(config_dir: Path = CONFIG_DIR) -> dict[str, str | None]:
    """Return {agent_name: raw_schema_path_or_None}."""
    return {
        name: cfg.output_schema for name, cfg in agent_config_reader(config_dir).items()
    }


def get_tool_map(config_dir: Path = CONFIG_DIR) -> dict[str, list[Any]]:
    """Return {agent_name: [tool_objects]}.

    Each agent receives all dynagent-layer tools from the registry.
    Tools listed in agents.yaml that are not in the registry are silently skipped.
    """
    from dynagent.tools.tool_registry import get_tools

    all_tools = get_tools()
    return {name: list(all_tools) for name in agent_config_reader(config_dir)}
