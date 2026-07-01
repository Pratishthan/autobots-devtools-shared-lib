# ABOUTME: Unit tests for the deep-agent engine state schema.
# ABOUTME: Verifies DynaDeepAgent extends DeepAgentState with identity keys.

from autobots_devtools_shared_lib.dynagent.models.deep_state import DynaDeepAgent


def test_dyna_deep_agent_declares_identity_keys():
    annotations = DynaDeepAgent.__annotations__
    assert "agent_name" in annotations
    assert "session_id" in annotations
    assert "user_name" in annotations
