# ABOUTME: Unit tests for agent configuration loading.
# ABOUTME: Tests YAML config parsing for agent configs via dynagent.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    AgentConfig,
    _reset_agent_config,
    load_agents_config,
)


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory with sample agent config."""
    agents_yaml = """
agents:
  coordinator:
    prompt: "coordinator"
    tools:
      - "handoff"
      - "get_document_status"
      - "list_documents"

  preface_agent:
    section: "01-preface"
    prompt: "01-preface"
    output_schema: "01-preface.json"
    approach: "qa"
    tools:
      - "read_file"
      - "update_section"

  entity_agent:
    section: "05-entities"
    prompt: "05-entity"
    output_schema: "05-entity.json"
    approach: "template"
    dynamic: true
    tools:
      - "read_file"
      - "update_section"
      - "create_entity"
"""
    (tmp_path / "agents.yaml").write_text(agents_yaml)
    _reset_agent_config()
    monkeypatch.setenv("DYNAGENT_CONFIG_ROOT_DIR", str(tmp_path))
    return tmp_path


class TestLoadAgentsConfig:
    """Tests for loading agents.yaml (via dynagent.load_agents_config)."""

    def test_loads_agents(self, config_dir: Path) -> None:  # noqa: ARG002
        """load_agents_config should return a dict of agent configs."""
        agents = load_agents_config()

        assert len(agents) == 3
        assert "coordinator" in agents
        assert "preface_agent" in agents
        assert "entity_agent" in agents

    def test_agent_has_prompt(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have a prompt path."""
        agents = load_agents_config()

        assert agents["coordinator"].prompt == "coordinator"

    def test_agent_has_tools(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have a list of tools."""
        agents = load_agents_config()

        assert "handoff" in agents["coordinator"].tools
        assert "get_document_status" in agents["coordinator"].tools

    def test_agent_has_section_reference(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have optional section reference."""
        agents = load_agents_config()

        assert agents["preface_agent"].section == "01-preface"
        assert agents["coordinator"].section is None

    def test_agent_has_approach(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have optional approach."""
        agents = load_agents_config()

        assert agents["preface_agent"].approach == "qa"
        assert agents["entity_agent"].approach == "template"

    def test_agent_has_output_schema(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have optional output schema."""
        agents = load_agents_config()

        assert agents["preface_agent"].output_schema == "01-preface.json"

    def test_agent_has_dynamic_flag(self, config_dir: Path) -> None:  # noqa: ARG002
        """Agent config should have optional dynamic flag."""
        agents = load_agents_config()

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
