# ABOUTME: Unit tests for the configurable agents-config filename.
# ABOUTME: Verifies the default is agents.yaml and load_agents_config honors overrides.


import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings


def test_default_filename_is_agents_yaml():
    assert DynagentSettings().agents_config_filename == "agents.yaml"


@pytest.fixture(autouse=True)
def _reset():
    _reset_agent_config()
    yield
    _reset_agent_config()


def test_load_reads_custom_filename(tmp_path, monkeypatch):
    (tmp_path / "deep-agents.yaml").write_text(
        "agents:\n  assistant:\n    prompt: assistant\n    is_default: true\n    tools: []\n"
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)

    settings = DynagentSettings(agents_config_filename="deep-agents.yaml")
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)

    agents = load_agents_config()
    assert set(agents.keys()) == {"assistant"}
    assert agents["assistant"].is_default is True
