# ABOUTME: State schema for the dynagent reference architecture.
# ABOUTME: Dynagent holds agent_name, session_id, and optional user_name (e.g. logged-in user id).

from typing import NotRequired

from langchain.agents import AgentState


class Dynagent(AgentState):
    """Minimal agent state carrying routing keys and optional user identity."""

    agent_name: NotRequired[str]
    session_id: NotRequired[str]
    user_name: NotRequired[str]
