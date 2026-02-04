# ABOUTME: Unit tests for agent configuration utility functions.
# ABOUTME: Validates config loading helpers produce correct shapes from agents.yaml.

from dynagent.agents.agent_config_utils import (
    get_agent_list,
    get_output_map,
    get_prompt_map,
    get_schema_path_map,
)

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


def test_get_output_map_coordinator_is_none():
    output_map = get_output_map()
    assert output_map.get("coordinator") is None


def test_get_output_map_section_agents_have_classes():
    output_map = get_output_map()
    for agent in (
        "preface_agent",
        "getting_started_agent",
        "features_agent",
        "entity_agent",
    ):
        assert output_map.get(agent) is not None, f"{agent} should have an output class"


def test_get_schema_path_map_coordinator_is_none():
    schema_map = get_schema_path_map()
    assert schema_map.get("coordinator") is None


def test_get_schema_path_map_section_agents_have_expected_paths():
    schema_map = get_schema_path_map()
    expected = {
        "preface_agent": "vision-agent/01-preface.json",
        "getting_started_agent": "vision-agent/02-getting-started.json",
        "features_agent": "vision-agent/03-01-list-of-features.json",
        "entity_agent": "vision-agent/05-entity.json",
    }
    for agent, path in expected.items():
        assert schema_map.get(agent) == path, f"{agent} schema path mismatch"
