# ABOUTME: Tests that Dynagent state supports the mcp_auth field for MCP token storage.
# ABOUTME: Validates typed dict accepts mcp_auth without breaking existing fields.

from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


def test_dynagent_accepts_mcp_auth_field():
    """Dynagent state should accept an mcp_auth dict for MCP token storage."""
    state: Dynagent = {
        "messages": [],
        "agent_name": "test",
        "session_id": "s1",
        "mcp_auth": {"atlassian": "token-abc"},
    }
    assert state["mcp_auth"] == {"atlassian": "token-abc"}


def test_dynagent_mcp_auth_is_optional():
    """mcp_auth should be optional — existing state without it must still work."""
    state: Dynagent = {
        "messages": [],
        "agent_name": "test",
    }
    assert "mcp_auth" not in state


def test_dynagent_mcp_auth_multiple_servers():
    """mcp_auth should support tokens for multiple MCP servers."""
    state: Dynagent = {
        "messages": [],
        "mcp_auth": {
            "atlassian": "token-a",
            "internal_api": "token-b",
        },
    }
    assert state["mcp_auth"]["atlassian"] == "token-a"
    assert state["mcp_auth"]["internal_api"] == "token-b"
