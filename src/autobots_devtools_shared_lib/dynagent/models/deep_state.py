# ABOUTME: State schema for the dynagent deep-agent engine.
# ABOUTME: Extends deepagents' DeepAgentState with routing/identity keys.

from typing import NotRequired

from deepagents import DeepAgentState


class DynaDeepAgent(DeepAgentState):
    """Deep-agent state carrying routing keys and optional user identity.

    Mirrors Dynagent's identity keys, but on the deepagents base so it keeps
    deepagents' messages delta reducer and todo/file state channels.
    """

    agent_name: NotRequired[str]
    session_id: NotRequired[str]
    user_name: NotRequired[str]
