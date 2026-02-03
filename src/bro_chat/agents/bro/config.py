# ABOUTME: Step configuration management for bro agent.
# ABOUTME: Builds step config from agents.yaml and provides lazy initialization.

from pathlib import Path
from typing import Any

from bro_chat.agents.bro.tools import create_bro_tools
from bro_chat.config.section_config import load_agents_config
from bro_chat.models.outputs import (
    EntityOutput,
    FeaturesOutput,
    GettingStartedOutput,
    PrefaceOutput,
)
from bro_chat.services.document_store import DocumentStore
from bro_chat.utils.files import load_prompt

# Mapping from schema name to dataclass
SCHEMA_TO_MODEL = {
    "vision-agent/01-preface.json": PrefaceOutput,
    "vision-agent/02-getting-started.json": GettingStartedOutput,
    "vision-agent/03-01-list-of-features.json": FeaturesOutput,
    "vision-agent/05-entity.json": EntityOutput,
}


def build_step_config(
    tool_registry: dict[str, Any],
    config_dir: Path = Path("configs/vision-agent"),
) -> dict[str, dict[str, Any]]:
    """Build step configuration from agents.yaml configuration.

    Args:
        tool_registry: Dictionary mapping tool names to tool objects.
        config_dir: Directory containing agents.yaml configuration.

    Returns:
        Dictionary mapping agent_id to step configuration.
    """

    agents_config = load_agents_config(config_dir)
    step_config = {}

    for agent_id, agent_cfg in agents_config.items():
        # Map tool names to tool objects
        tool_objects = [tool_registry[name] for name in agent_cfg.tools]

        config_dict: dict[str, Any] = {
            "prompt": load_prompt(agent_cfg.prompt),
            "tools": tool_objects,
            "requires": [],  # Could also come from config if needed
        }

        # Map output_schema to response_format dataclass
        if agent_cfg.output_schema:
            response_format = SCHEMA_TO_MODEL.get(agent_cfg.output_schema)
            if response_format:
                config_dict["response_format"] = response_format

        step_config[agent_id] = config_dict

    return step_config


# Global step config (initialized lazily)
BRO_STEP_CONFIG: dict[str, dict[str, Any]] = {}


def get_step_config(store: DocumentStore) -> dict[str, dict[str, Any]]:
    """Get or create step configuration."""
    global BRO_STEP_CONFIG
    if not BRO_STEP_CONFIG:
        tool_registry = create_bro_tools(store)
        BRO_STEP_CONFIG = build_step_config(tool_registry)
    return BRO_STEP_CONFIG


def get_schema_for_agent(
    agent_id: str, config_dir: Path = Path("configs/vision-agent")
) -> str | None:
    """Get the output schema path for a given agent.

    Args:
        agent_id: Agent identifier (e.g., "preface_agent").
        config_dir: Directory containing agents.yaml configuration.

    Returns:
        Schema path (e.g., "vision-agent/01-preface.json") or None if not configured.
    """
    agents_config = load_agents_config(config_dir)
    agent_cfg = agents_config.get(agent_id)
    return agent_cfg.output_schema if agent_cfg else None
