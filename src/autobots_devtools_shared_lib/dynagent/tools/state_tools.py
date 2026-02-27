# ABOUTME: State management tools for the dynagent workflow.
# ABOUTME: Provides command helpers and handoff logic.

from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

logger = get_logger(__name__)


# --- Command helpers ---


def error_cmd(message: str, tool_call_id: str) -> Command:
    """Create a Command for error/validation failure responses."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def transition_cmd(message: str, tool_call_id: str, new_agent: str, **updates: Any) -> Command:
    """Create a Command for successful agent transitions."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ],
            "agent_name": new_agent,
            **updates,
        }
    )


# --- Handoff validation (extracted for testability) ---


def _validate_handoff(next_agent: str) -> str | None:
    """Validate agent name against config. Returns error string or None."""
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
        get_agent_list,
    )

    valid = get_agent_list()
    if next_agent not in valid:
        return f"Invalid agent: {next_agent}. Valid agents: {', '.join(valid)}"
    return None


# --- Tools ---


@tool
def get_agent_list() -> str:
    """Return list of available agent names."""
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
        get_agent_list as _list_agents,
    )

    agents = _list_agents()
    logger.info(f"Agent list requested: {agents}")
    return ", ".join(agents)


@tool
def handoff(runtime: ToolRuntime[None, Dynagent], next_agent: str) -> Command:
    """Transition to a different agent."""
    error = _validate_handoff(next_agent)
    if error:
        return error_cmd(error, runtime.tool_call_id or "unknown")

    logger.info(f"Handoff to {next_agent}")
    return transition_cmd(
        f"Handoff to {next_agent}",
        runtime.tool_call_id or "unknown",
        next_agent,
    )
