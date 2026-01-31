# ABOUTME: Integration tests for the main bro agent.
# ABOUTME: Tests agent creation, state management, and step configuration.

from pathlib import Path

import pytest

from bro_chat.agents.bro import (
    BroAgentState,
    create_bro_agent,
    get_bro_agent_list,
    get_step_config,
)
from bro_chat.services.document_store import DocumentStore


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


class TestBroAgentState:
    """Tests for BroAgentState."""

    def test_state_has_current_step(self) -> None:
        """BroAgentState should track current step."""
        state: BroAgentState = {
            "messages": [],
            "current_step": "coordinator",
        }
        assert state["current_step"] == "coordinator"

    def test_state_has_document_context(self) -> None:
        """BroAgentState should track document context."""
        state: BroAgentState = {
            "messages": [],
            "current_step": "coordinator",
            "component": "payment-gateway",
            "version": "v1",
        }
        assert state["component"] == "payment-gateway"
        assert state["version"] == "v1"


class TestBroAgentList:
    """Tests for agent list loaded from config."""

    def test_includes_coordinator(self) -> None:
        """Agent list should include coordinator."""
        agents = get_bro_agent_list()
        assert "coordinator" in agents

    def test_includes_agents_from_config(self) -> None:
        """Agent list should match agents.yaml config."""
        from bro_chat.config.section_config import load_agents_config

        agents = get_bro_agent_list()
        expected = load_agents_config(Path("configs/vision-agent"))

        assert set(agents) == set(expected.keys())

    def test_all_agents_have_config(self) -> None:
        """All agents in list should have valid configurations."""
        from bro_chat.config.section_config import load_agents_config

        agents = get_bro_agent_list()
        agents_config = load_agents_config(Path("configs/vision-agent"))

        for agent in agents:
            assert agent in agents_config
            config = agents_config[agent]
            assert config.prompt
            assert config.tools


class TestBroStepConfig:
    """Tests for BRO_STEP_CONFIG."""

    def test_coordinator_has_config(self, temp_store: DocumentStore) -> None:
        """Coordinator should have step configuration."""
        step_config = get_step_config(temp_store)
        assert "coordinator" in step_config
        config = step_config["coordinator"]
        assert "prompt" in config
        assert "tools" in config

    def test_section_agents_have_config(self, temp_store: DocumentStore) -> None:
        """All agents from config should have step configurations."""
        from bro_chat.config.section_config import load_agents_config

        step_config = get_step_config(temp_store)
        agents_config = load_agents_config(Path("configs/vision-agent"))

        for agent_id in agents_config:
            assert agent_id in step_config
            config = step_config[agent_id]
            assert "prompt" in config
            assert "tools" in config


class TestCreateBroAgent:
    """Tests for create_bro_agent factory."""

    def test_creates_agent(self, temp_store: DocumentStore) -> None:
        """Factory should create a bro agent."""
        agent = create_bro_agent(store=temp_store)
        assert agent is not None

    def test_agent_has_name(self, temp_store: DocumentStore) -> None:
        """Agent should have the correct name."""
        agent = create_bro_agent(store=temp_store)
        assert agent.name == "bro-agent"

    def test_agent_has_set_document_context_tool(
        self, temp_store: DocumentStore
    ) -> None:
        """Agent should have set_document_context tool available."""
        from bro_chat.agents.bro import create_bro_tools

        tools = create_bro_tools(temp_store)
        assert "set_document_context" in tools
