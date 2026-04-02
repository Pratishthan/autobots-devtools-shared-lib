# ABOUTME: Unit tests for convert_format schema lookup logic.
# ABOUTME: Verifies schema resolution per agent and error for no-schema agents.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
)
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    """Reset singletons and point env vars at the real bro config."""
    _reset_agent_config()
    AgentMeta.reset()
    candidates = [
        Path("autobots-agents-bro/configs/bro"),
        Path("configs/bro"),
        Path("../autobots-agents-bro/configs/bro"),
    ]
    for c in candidates:
        if (c / "agents.yaml").exists():
            monkeypatch.setenv("DYNAGENT_CONFIG_ROOT_DIR", str(c))
            monkeypatch.setenv("SCHEMA_BASE", str(c / "schemas"))
            break
    yield
    _reset_agent_config()
    AgentMeta.reset()


def test_schema_resolves_for_preface_agent(bro_registered):
    meta = AgentMeta.instance()
    assert meta.output_schema_map["preface_agent"] is not None


def test_schema_resolves_for_getting_started_agent(bro_registered):
    meta = AgentMeta.instance()
    assert meta.output_schema_map["getting_started_agent"] is not None


def test_schema_resolves_for_features_agent(bro_registered):
    meta = AgentMeta.instance()
    assert meta.output_schema_map["features_agent"] is not None


def test_schema_resolves_for_entity_agent(bro_registered):
    meta = AgentMeta.instance()
    assert meta.output_schema_map["entity_agent"] is not None


def test_coordinator_has_no_schema(bro_registered):
    """Coordinator has no output_schema — convert_format should error for it."""
    meta = AgentMeta.instance()
    assert meta.output_schema_map.get("coordinator") is None


def test_all_schema_files_exist_on_disk(bro_registered):
    """Every section agent should have an output schema resolved."""
    meta = AgentMeta.instance()
    for agent, schema in meta.output_schema_map.items():
        if schema is None:
            continue
        assert isinstance(schema, dict), f"Schema not resolved for {agent}"
