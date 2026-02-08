# ABOUTME: Unit tests for agent configuration utility functions.
# ABOUTME: Validates config loading helpers produce correct shapes from agents.yaml.

import logging
from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_agent_list,
    get_prompt_map,
    get_schema_path_map,
    get_tool_map,
)

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "bro"


@pytest.fixture(autouse=True)
def setup_config_dir(monkeypatch):
    """Point config dir at local fixture data and clear cache for each test."""
    _reset_agent_config()
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: _CONFIG_DIR,
    )
    yield
    _reset_agent_config()


EXPECTED_AGENTS = {
    "coordinator",
    "preface_agent",
    "getting_started_agent",
    "features_agent",
    "entity_agent",
}


def test_get_agent_list_returns_all_five():
    agents = get_agent_list()
    assert set(agents) == EXPECTED_AGENTS


def test_get_agent_list_returns_list():
    agents = get_agent_list()
    assert isinstance(agents, list)


def test_get_prompt_map_has_all_agents():
    prompt_map = get_prompt_map()
    assert set(prompt_map.keys()) == EXPECTED_AGENTS


def test_get_prompt_map_values_are_non_empty_strings():
    prompt_map = get_prompt_map()
    for name, prompt in prompt_map.items():
        assert isinstance(prompt, str), f"{name} prompt is not a string"
        assert len(prompt) > 0, f"{name} prompt is empty"


def test_get_schema_path_map_coordinator_is_none():
    schema_map = get_schema_path_map()
    assert schema_map.get("coordinator") is None


def test_get_schema_path_map_section_agents_have_expected_paths():
    schema_map = get_schema_path_map()
    expected = {
        "preface_agent": "01-preface.json",
        "getting_started_agent": "02-getting-started.json",
        "features_agent": "03-01-list-of-features.json",
        "entity_agent": "05-entity.json",
    }
    for agent, path in expected.items():
        assert schema_map.get(agent) == path, f"{agent} schema path mismatch"


def test_get_tool_map_resolves_per_agent(bro_registered):
    """With BRO registered, every agent's listed tools resolve to real tool objects."""
    tool_map = get_tool_map()
    # Coordinator should have its listed tools (including BRO ones)
    coord_names = {t.name for t in tool_map["coordinator"]}
    assert "handoff" in coord_names

    # Section agents should have convert_format
    for agent in ("preface_agent", "getting_started_agent", "features_agent"):
        names = {t.name for t in tool_map[agent]}
        assert "update_section" in names, f"{agent} missing update_section"

    # Entity agent has entity tools
    entity_names = {t.name for t in tool_map["entity_agent"]}
    assert "create_entity" in entity_names
    assert "list_entities" in entity_names
    assert "delete_entity" in entity_names


def test_get_tool_map_warns_on_unresolved(caplog):
    """Without BRO registration, BRO tools are unresolved → warning logged."""
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import (
        _reset_usecase_tools,
    )

    _reset_usecase_tools()
    with caplog.at_level(logging.WARNING):
        tool_map = get_tool_map()

    # BRO tools like create_document should be absent from coordinator
    coord_names = {t.name for t in tool_map["coordinator"]}
    assert "create_document" not in coord_names

    # And a warning should have been logged
    assert any("unresolved tool" in r.message for r in caplog.records)

    # Cleanup
    _reset_usecase_tools()
