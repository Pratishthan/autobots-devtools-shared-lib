# ABOUTME: Configuration loader for vision agent sections and agents.
# ABOUTME: Parses YAML files into typed SectionConfig and AgentConfig dataclasses.

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SectionConfig:
    """Configuration for a vision document section."""

    section_id: str
    title: str
    description: str
    static: bool = False
    dynamic: bool = False
    subsections: list[str] = field(default_factory=list)
    item_prefix: str | None = None

    @classmethod
    def from_dict(cls, section_id: str, data: dict[str, Any]) -> "SectionConfig":
        """Create SectionConfig from a dictionary."""
        return cls(
            section_id=section_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            static=data.get("static", False),
            dynamic=data.get("dynamic", False),
            subsections=data.get("subsections", []),
            item_prefix=data.get("item_prefix"),
        )


@dataclass
class AgentConfig:
    """Configuration for a vision agent."""

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


def load_sections_config(config_dir: Path | str) -> dict[str, SectionConfig]:
    """Load section configurations from sections.yaml.

    Args:
        config_dir: Directory containing sections.yaml.

    Returns:
        Dictionary mapping section_id to SectionConfig.
    """
    config_path = Path(config_dir) / "sections.yaml"

    with open(config_path) as f:
        data = yaml.safe_load(f)

    sections = {}
    for section_id, section_data in data.get("sections", {}).items():
        sections[section_id] = SectionConfig.from_dict(section_id, section_data)

    logger.info(f"Loaded {len(sections)} section configs from {config_path}")
    return sections


def load_agents_config(config_dir: Path | str) -> dict[str, AgentConfig]:
    """Load agent configurations from agents.yaml.

    Args:
        config_dir: Directory containing agents.yaml.

    Returns:
        Dictionary mapping agent_id to AgentConfig.
    """
    config_path = Path(config_dir) / "agents.yaml"

    with open(config_path) as f:
        data = yaml.safe_load(f)

    agents = {}
    for agent_id, agent_data in data.get("agents", {}).items():
        agents[agent_id] = AgentConfig.from_dict(agent_id, agent_data)

    logger.info(f"Loaded {len(agents)} agent configs from {config_path}")
    return agents
