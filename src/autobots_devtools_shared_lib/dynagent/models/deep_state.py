# ABOUTME: State schema for the dynagent deep-agent engine.
# ABOUTME: Extends deepagents' DeepAgentState with routing/identity keys.

from typing import Annotated, NotRequired

from deepagents import DeepAgentState


def _keep(left: str | None, right: str | None) -> str | None:
    """Fold concurrent writes to an identity key from parallel subagents.

    deepagents seeds each subagent with the parent state and echoes non-excluded
    keys back on completion. When subagents run in parallel, several identical
    identity-key writes land in one super-step; a plain LastValue channel rejects
    that with InvalidUpdateError. All branches carry the same value, so keeping
    the latest non-null value resolves the collision safely.
    """
    return right if right is not None else left


class DynaDeepAgent(DeepAgentState):
    """Deep-agent state carrying routing keys and optional user identity.

    Mirrors Dynagent's identity keys, but on the deepagents base so it keeps
    deepagents' messages delta reducer and todo/file state channels. Identity
    keys use a fold reducer so parallel subagents echoing them back do not
    collide on the LastValue channel.
    """

    agent_name: NotRequired[Annotated[str, _keep]]
    session_id: NotRequired[Annotated[str, _keep]]
    user_name: NotRequired[Annotated[str, _keep]]
