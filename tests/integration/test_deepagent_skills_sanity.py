# ABOUTME: Sanity test - deep engine with skills + memory on a FilesystemBackend domain.
# ABOUTME: Builds a temp AMA-style domain; requires ANTHROPIC_API_KEY (skipped otherwise).

import os

import pytest

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as cfg
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import _reset_agent_config
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.base_deepagent import create_base_deepagent
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    DynagentSettings,
    LLMProvider,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY"),
]

SKILL_MD = """---
name: favorite-color
description: Answers questions about the project's favorite color.
---
When asked about the favorite color, answer exactly: TEAL-042.
"""


@pytest.fixture
def ama_domain(tmp_path, monkeypatch):
    _reset_agent_config()
    AgentMeta.reset()
    # The filesystem backend is built with virtual_mode=True (see deep_backend.py),
    # so skills/memory sources are virtual paths resolved *inside* root_dir, not raw
    # host paths. Skill and memory files must therefore live under `workspace`
    # (the backend root), referenced by their root-relative virtual path.
    workspace = tmp_path / "workspace"
    skills_dir = workspace / "skills" / "favorite-color"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(SKILL_MD)
    (workspace / "AGENTS.md").write_text("# Conventions\nThis project loves precise answers.\n")

    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "assistant.md").write_text(
        "You are a helpful assistant. Use your skills to answer exactly."
    )
    (tmp_path / "deep-agents.yaml").write_text(
        f"""
default_backend:
  type: filesystem
  root_dir: {workspace}

agents:
  assistant:
    prompt: assistant
    is_default: true
    tools: []
    skills: ["/skills/"]
    memory: ["/AGENTS.md"]
"""
    )
    settings = DynagentSettings(
        agents_config_filename="deep-agents.yaml",
        llm_provider=LLMProvider.ANTHROPIC,
        llm_model="claude-sonnet-4-6",
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "get_dynagent_settings", lambda: settings)
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.llm.llm.get_dynagent_settings", lambda: settings
    )
    yield
    _reset_agent_config()
    AgentMeta.reset()


def test_agent_reads_skill_and_answers(ama_domain):
    agent = create_base_deepagent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is the project's favorite color?"}]},
        config={"configurable": {"thread_id": "sanity-1"}, "recursion_limit": 50},
    )
    final_text = str(result["messages"][-1].content)
    assert "TEAL-042" in final_text
