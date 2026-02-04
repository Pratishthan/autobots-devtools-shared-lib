# ABOUTME: Unit tests for section configuration loading.
# ABOUTME: Tests YAML config parsing for sections and agent configs.

from pathlib import Path

import pytest

from bro_chat.config.section_config import (
    SectionConfig,
    load_sections_config,
)
from dynagent.agents.agent_config_utils import AgentConfig, _load_agents_config


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with sample configs."""
    vision_dir = tmp_path / "vision-agent"
    vision_dir.mkdir()

    sections_yaml = """
sections:
  01-preface:
    title: "Preface"
    description: "About this guide, audience, references, and glossary"
    static: true
    subsections:
      - "11-about-this-guide"
      - "12-audience"
      - "13-reference-documents"
      - "14-glossary"

  02-getting-started:
    title: "Getting Started"
    description: "Overview and vision of the component"
    static: true

  05-entities:
    title: "Entities"
    description: "Entity and meta attribute details"
    dynamic: true
    item_prefix: "05-entity"
"""
    (vision_dir / "sections.yaml").write_text(sections_yaml)

    agents_yaml = """
agents:
  coordinator:
    prompt: "vision-agent/coordinator"
    tools:
      - "handoff"
      - "get_document_status"
      - "list_documents"

  preface_agent:
    section: "01-preface"
    prompt: "vision-agent/01-preface"
    output_schema: "vision-agent/01-preface.json"
    approach: "qa"
    tools:
      - "read_file"
      - "update_section"

  entity_agent:
    section: "05-entities"
    prompt: "vision-agent/05-entity"
    output_schema: "vision-agent/05-entity.json"
    approach: "template"
    dynamic: true
    tools:
      - "read_file"
      - "update_section"
      - "create_entity"
"""
    (vision_dir / "agents.yaml").write_text(agents_yaml)

    return tmp_path


class TestLoadSectionsConfig:
    """Tests for loading sections.yaml."""

    def test_loads_sections(self, config_dir: Path) -> None:
        """load_sections_config should return a dict of section configs."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert len(sections) == 3
        assert "01-preface" in sections
        assert "02-getting-started" in sections
        assert "05-entities" in sections

    def test_section_has_title(self, config_dir: Path) -> None:
        """Section config should have a title."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert sections["01-preface"].title == "Preface"

    def test_section_has_description(self, config_dir: Path) -> None:
        """Section config should have a description."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert "audience" in sections["01-preface"].description.lower()

    def test_section_has_static_flag(self, config_dir: Path) -> None:
        """Section config should have static/dynamic flags."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert sections["01-preface"].static is True
        assert sections["05-entities"].dynamic is True

    def test_section_has_subsections(self, config_dir: Path) -> None:
        """Section config should have optional subsections."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert "11-about-this-guide" in sections["01-preface"].subsections

    def test_dynamic_section_has_item_prefix(self, config_dir: Path) -> None:
        """Dynamic section should have an item prefix."""
        sections = load_sections_config(config_dir / "vision-agent")

        assert sections["05-entities"].item_prefix == "05-entity"


class TestLoadAgentsConfig:
    """Tests for loading agents.yaml (via dynagent._load_agents_config)."""

    def test_loads_agents(self, config_dir: Path) -> None:
        """_load_agents_config should return a dict of agent configs."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert len(agents) == 3
        assert "coordinator" in agents
        assert "preface_agent" in agents
        assert "entity_agent" in agents

    def test_agent_has_prompt(self, config_dir: Path) -> None:
        """Agent config should have a prompt path."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert agents["coordinator"].prompt == "vision-agent/coordinator"

    def test_agent_has_tools(self, config_dir: Path) -> None:
        """Agent config should have a list of tools."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert "handoff" in agents["coordinator"].tools
        assert "get_document_status" in agents["coordinator"].tools

    def test_agent_has_section_reference(self, config_dir: Path) -> None:
        """Agent config should have optional section reference."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert agents["preface_agent"].section == "01-preface"
        assert agents["coordinator"].section is None

    def test_agent_has_approach(self, config_dir: Path) -> None:
        """Agent config should have optional approach."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert agents["preface_agent"].approach == "qa"
        assert agents["entity_agent"].approach == "template"

    def test_agent_has_output_schema(self, config_dir: Path) -> None:
        """Agent config should have optional output schema."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert agents["preface_agent"].output_schema == "vision-agent/01-preface.json"

    def test_agent_has_dynamic_flag(self, config_dir: Path) -> None:
        """Agent config should have optional dynamic flag."""
        agents = _load_agents_config(config_dir / "vision-agent")

        assert agents["entity_agent"].dynamic is True
        assert agents["preface_agent"].dynamic is False


class TestSectionConfig:
    """Tests for SectionConfig dataclass."""

    def test_create_minimal(self) -> None:
        """SectionConfig should be creatable with minimal params."""
        config = SectionConfig(
            section_id="01-preface",
            title="Preface",
            description="About this guide",
        )

        assert config.section_id == "01-preface"
        assert config.static is False
        assert config.dynamic is False
        assert config.subsections == []

    def test_defaults(self) -> None:
        """SectionConfig should have sensible defaults."""
        config = SectionConfig(
            section_id="test",
            title="Test",
            description="Test section",
        )

        assert config.item_prefix is None


class TestAgentConfig:
    """Tests for AgentConfig dataclass (now in dynagent.agents.agent_config_utils)."""

    def test_create_minimal(self) -> None:
        """AgentConfig should be creatable with minimal params."""
        config = AgentConfig(
            agent_id="test_agent",
            prompt="test/prompt",
            tools=["handoff"],
        )

        assert config.agent_id == "test_agent"
        assert config.section is None
        assert config.approach is None
        assert config.dynamic is False

    def test_defaults(self) -> None:
        """AgentConfig should have sensible defaults."""
        config = AgentConfig(
            agent_id="test",
            prompt="test/prompt",
            tools=[],
        )

        assert config.output_schema is None
        assert config.dynamic is False
