# ABOUTME: Unit tests for Dynagent state schema.
# ABOUTME: Verifies state class structure and NotRequired field definitions.

from langchain.agents import AgentState

from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


def test_dynagent_is_agent_state_subclass():
    # TypedDict metaclass doesn't expose parents in __mro__ or __bases__;
    # verify by checking that all AgentState required keys are inherited.
    assert AgentState.__required_keys__.issubset(Dynagent.__required_keys__)


def test_dynagent_has_agent_name():
    assert "agent_name" in Dynagent.__annotations__


def test_dynagent_has_session_id():
    assert "session_id" in Dynagent.__annotations__


def test_dynagent_agent_name_is_optional():
    """agent_name must be NotRequired — present in optional_keys, not required_keys."""
    assert "agent_name" in Dynagent.__optional_keys__
    assert "agent_name" not in Dynagent.__required_keys__


def test_dynagent_session_id_is_optional():
    """session_id must be NotRequired — present in optional_keys, not required_keys."""
    assert "session_id" in Dynagent.__optional_keys__
    assert "session_id" not in Dynagent.__required_keys__


def test_dynagent_has_user_name():
    assert "user_name" in Dynagent.__annotations__


def test_dynagent_user_name_is_optional():
    """user_name must be NotRequired (e.g. logged-in user identifier)."""
    assert "user_name" in Dynagent.__optional_keys__
    assert "user_name" not in Dynagent.__required_keys__


def test_dynagent_only_adds_agent_name_session_id_user_name():
    """Dynagent extends AgentState with routing/identity keys only."""
    own_fields = set(Dynagent.__annotations__.keys()) - set(AgentState.__annotations__.keys())
    assert own_fields == {"agent_name", "session_id", "user_name"}
