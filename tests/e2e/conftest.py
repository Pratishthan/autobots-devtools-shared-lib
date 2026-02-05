# ABOUTME: End-to-end test fixtures for bro-chat.
# ABOUTME: Ensures BRO tools are registered before any agent creation call.

import pytest


@pytest.fixture(autouse=True)
def bro_registered_e2e():
    """Register BRO tools for every e2e test; reset after."""
    from bro_chat.agents.bro_tools import register_bro_tools
    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import _reset_usecase_tools

    _reset_usecase_tools()
    AgentMeta.reset()
    register_bro_tools()
    yield
    _reset_usecase_tools()
    AgentMeta.reset()
