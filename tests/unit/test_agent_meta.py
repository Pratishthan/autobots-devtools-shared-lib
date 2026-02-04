# ABOUTME: Unit tests for AgentMeta singleton.
# ABOUTME: Verifies lazy loading, correct maps, and test-isolation reset.

import pytest

from dynagent.agents.agent_meta import AgentMeta

EXPECTED_AGENTS = {
    "coordinator",
    "preface_agent",
    "getting_started_agent",
    "features_agent",
    "entity_agent",
}


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure clean singleton state for each test."""
    AgentMeta.reset()
    yield
    AgentMeta.reset()


def test_singleton_returns_same_instance():
    a = AgentMeta.instance()
    b = AgentMeta.instance()
    assert a is b


def test_reset_clears_singleton():
    a = AgentMeta.instance()
    AgentMeta.reset()
    b = AgentMeta.instance()
    assert a is not b


def test_prompt_map_has_all_agents():
    meta = AgentMeta.instance()
    assert set(meta.prompt_map.keys()) == EXPECTED_AGENTS


def test_prompt_map_values_are_non_empty_strings():
    meta = AgentMeta.instance()
    for name, prompt in meta.prompt_map.items():
        assert isinstance(prompt, str)
        assert len(prompt) > 0, f"{name} has empty prompt"


def test_output_struct_map_coordinator_is_none():
    meta = AgentMeta.instance()
    assert meta.output_struct_map.get("coordinator") is None


def test_output_struct_map_section_agents_populated(bro_registered):  # noqa: ARG001
    """Output structs are populated only after BRO registration."""
    meta = AgentMeta.instance()
    for agent in (
        "preface_agent",
        "getting_started_agent",
        "features_agent",
        "entity_agent",
    ):
        assert (
            meta.output_struct_map.get(agent) is not None
        ), f"{agent} output_struct_map is None"


def test_schema_path_map_coordinator_is_none():
    meta = AgentMeta.instance()
    assert meta.schema_path_map.get("coordinator") is None


def test_schema_path_map_section_agents_populated():
    meta = AgentMeta.instance()
    for agent in (
        "preface_agent",
        "getting_started_agent",
        "features_agent",
        "entity_agent",
    ):
        assert (
            meta.schema_path_map.get(agent) is not None
        ), f"{agent} schema_path_map is None"


def test_tool_map_has_all_agents():
    meta = AgentMeta.instance()
    assert set(meta.tool_map.keys()) == EXPECTED_AGENTS


def test_tool_map_values_are_non_empty_lists(bro_registered):  # noqa: ARG001
    """With BRO registered, every agent resolves at least its listed tools."""
    meta = AgentMeta.instance()
    for name, tools in meta.tool_map.items():
        assert isinstance(tools, list), f"{name} tool_map value is not a list"
        assert len(tools) > 0, f"{name} has no tools"
