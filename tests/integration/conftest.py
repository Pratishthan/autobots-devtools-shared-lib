# ABOUTME: Integration-test fixtures for bro-chat.
# ABOUTME: Ensures BRO tools are registered before any agent creation call.

import pytest


@pytest.fixture(autouse=True)
def bro_registered_integration():
    """Register BRO tools for every integration test; reset after."""
    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import (
        _reset_usecase_tools,
    )

    _reset_usecase_tools()
    AgentMeta.reset()
    yield
    _reset_usecase_tools()
    AgentMeta.reset()
