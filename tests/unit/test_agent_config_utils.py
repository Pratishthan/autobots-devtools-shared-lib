# ABOUTME: Unit tests for agent configuration utility functions.
# ABOUTME: Validates config loading helpers produce correct shapes from agents.yaml.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_agent_list,
    get_prompt_map,
    get_schema_map,
    get_schema_path_map,
    get_tool_map,
    load_schema,
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


def test_get_tool_map_raises_on_unresolved():
    """Without BRO registration, BRO tools are unresolved → ValueError raised."""
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import _reset_usecase_tools

    _reset_usecase_tools()

    # Should raise ValueError when encountering unresolved tools
    with pytest.raises(ValueError, match=r"Unresolved tool .* for agent"):
        get_tool_map()

    # Cleanup
    _reset_usecase_tools()


def test_get_schema_map_coordinator_is_none():
    """Coordinator has no output_schema, should get None in schema_map."""
    schema_map = get_schema_map()
    assert schema_map.get("coordinator") is None


def test_get_schema_map_section_agents_have_parsed_schemas():
    """Section agents should have parsed schema dicts, not paths."""
    schema_map = get_schema_map()

    agents_with_schemas = [
        "preface_agent",
        "getting_started_agent",
        "features_agent",
        "entity_agent",
    ]

    for agent in agents_with_schemas:
        schema = schema_map.get(agent)
        assert schema is not None, f"{agent} schema is None"
        assert isinstance(schema, dict), f"{agent} schema is not a dict"
        assert "type" in schema, f"{agent} schema missing 'type' field"


def test_get_schema_map_all_agents_present():
    """schema_map should have entries for all agents."""
    schema_map = get_schema_map()
    agent_list = get_agent_list()
    assert set(schema_map.keys()) == set(agent_list)


def test_load_schema_missing_file_raises_error(tmp_path, monkeypatch):
    """load_schema should raise FileNotFoundError for missing files."""
    # Point to tmp dir with no schemas
    monkeypatch.setenv("DYNAGENT_CONFIG_ROOT_DIR", str(tmp_path))
    (tmp_path / "agents.yaml").write_text("agents: {}")
    _reset_agent_config()

    with pytest.raises(FileNotFoundError, match="Schema file not found"):
        load_schema("missing.json")


def test_load_schema_invalid_json_raises_error(tmp_path, monkeypatch):
    """load_schema should raise ValueError for invalid JSON."""
    # Create schema directory and bad JSON file
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "bad.json").write_text("{invalid json")

    # Patch get_config_dir to return tmp_path
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_schema("bad.json")
