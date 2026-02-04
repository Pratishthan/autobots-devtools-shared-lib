# ABOUTME: Unit tests for convert_format schema lookup logic.
# ABOUTME: Verifies schema resolution per agent and error for no-schema agents.

from pathlib import Path

import pytest

from dynagent.agents.agent_meta import AgentMeta


@pytest.fixture(autouse=True)
def reset_singleton():
    AgentMeta.reset()
    yield
    AgentMeta.reset()


def test_schema_resolves_for_preface_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["preface_agent"] == "vision-agent/01-preface.json"


def test_schema_resolves_for_getting_started_agent():
    meta = AgentMeta.instance()
    assert (
        meta.schema_path_map["getting_started_agent"]
        == "vision-agent/02-getting-started.json"
    )


def test_schema_resolves_for_features_agent():
    meta = AgentMeta.instance()
    assert (
        meta.schema_path_map["features_agent"]
        == "vision-agent/03-01-list-of-features.json"
    )


def test_schema_resolves_for_entity_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["entity_agent"] == "vision-agent/05-entity.json"


def test_coordinator_has_no_schema():
    """Coordinator has no output_schema — convert_format should error for it."""
    meta = AgentMeta.instance()
    assert meta.schema_path_map.get("coordinator") is None


def test_all_schema_files_exist_on_disk():
    """Every schema path in the map must point to a real file."""
    meta = AgentMeta.instance()
    for agent, path in meta.schema_path_map.items():
        if path is None:
            continue
        schema_file = Path("schemas") / path
        assert schema_file.exists(), f"Schema file missing for {agent}: {schema_file}"
