# ABOUTME: Unit tests for agent configuration loading.
# ABOUTME: Tests YAML config parsing for agent configs via dynagent.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import AgentConfig, _load_agents_config


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with sample agent config."""
    vision_dir = tmp_path / "vision-agent"
    vision_dir.mkdir()

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
