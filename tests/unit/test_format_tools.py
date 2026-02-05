# ABOUTME: Unit tests for convert_format schema lookup logic.
# ABOUTME: Verifies schema resolution per agent and error for no-schema agents.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
)
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.config.settings import get_settings


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


def test_schema_resolves_for_preface_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["preface_agent"] == "01-preface.json"


def test_schema_resolves_for_getting_started_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["getting_started_agent"] == "02-getting-started.json"


def test_schema_resolves_for_features_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["features_agent"] == "03-01-list-of-features.json"


def test_schema_resolves_for_entity_agent():
    meta = AgentMeta.instance()
    assert meta.schema_path_map["entity_agent"] == "05-entity.json"


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
        schema_file = get_settings().schema_base / path
        assert schema_file.exists(), f"Schema file missing for {agent}: {schema_file}"
