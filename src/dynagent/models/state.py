# ABOUTME: State schema for the dynagent reference architecture.
# ABOUTME: Dynagent holds agent_name and session_id as the only routing keys.

from typing import NotRequired

from langchain.agents import AgentState


class Dynagent(AgentState):
    """Minimal agent state carrying only routing keys."""

    agent_name: NotRequired[str]
    session_id: NotRequired[str]
