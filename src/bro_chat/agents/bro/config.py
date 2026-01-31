# ABOUTME: Step configuration management for bro agent.
# ABOUTME: Builds step config from agents.yaml and provides lazy initialization.

from pathlib import Path
from typing import Any

from bro_chat.agents.bro.tools import create_bro_tools
from bro_chat.config.section_config import load_agents_config
from bro_chat.services.document_store import DocumentStore
from bro_chat.utils.files import load_prompt


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

        step_config[agent_id] = {
            "prompt": load_prompt(agent_cfg.prompt),
            "tools": tool_objects,
            "requires": [],  # Could also come from config if needed
        }

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
