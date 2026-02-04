# ABOUTME: Configuration loader for vision document sections.
# ABOUTME: Parses sections.yaml into typed SectionConfig dataclasses.

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
