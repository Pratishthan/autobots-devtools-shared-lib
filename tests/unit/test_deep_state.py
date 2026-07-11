# ABOUTME: Unit tests for the deep-agent engine state schema.
# ABOUTME: Verifies DynaDeepAgent extends DeepAgentState with identity keys.

from langgraph.graph import END, START, StateGraph

from autobots_devtools_shared_lib.dynagent.models.deep_state import DynaDeepAgent


def test_dyna_deep_agent_declares_identity_keys():
    annotations = DynaDeepAgent.__annotations__
    assert "agent_name" in annotations
    assert "session_id" in annotations
    assert "user_name" in annotations


def test_parallel_writes_to_identity_keys_do_not_collide():
    """Parallel subagents each echo identity keys back; the state channel must fold
    concurrent writes instead of raising InvalidUpdateError (LastValue collision).

    Reproduces the AMA parallel-subagent crash: two nodes in one super-step both
    write session_id/user_name/agent_name.
    """

    def echo(_state: DynaDeepAgent) -> dict:
        return {"session_id": "s1", "user_name": "u1", "agent_name": "a1"}

    builder = StateGraph(DynaDeepAgent)
    builder.add_node("branch_a", echo)
    builder.add_node("branch_b", echo)
    builder.add_edge(START, "branch_a")
    builder.add_edge(START, "branch_b")
    builder.add_edge("branch_a", END)
    builder.add_edge("branch_b", END)
    graph = builder.compile()

    result = graph.invoke({"messages": []})

    assert result["session_id"] == "s1"
    assert result["user_name"] == "u1"
    assert result["agent_name"] == "a1"
