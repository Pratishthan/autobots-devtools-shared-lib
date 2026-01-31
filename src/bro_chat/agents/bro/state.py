# ABOUTME: State management for bro agent workflow.
# ABOUTME: Defines BroAgentState and command helper functions for state transitions.

from pathlib import Path
from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain.messages import ToolMessage
from langgraph.types import Command


def get_bro_agent_list(
    config_dir: Path = Path("configs/vision-agent"),
) -> list[str]:
    """Return list of available bro agent names from config.

    Args:
        config_dir: Directory containing agents.yaml configuration.

    Returns:
        List of agent names defined in configuration.
    """
    from bro_chat.config.section_config import load_agents_config

    agents_config = load_agents_config(config_dir)
    return list(agents_config.keys())


class BroAgentState(AgentState):
    """State for the bro agent workflow."""

    current_step: NotRequired[str]
    component: NotRequired[str]
    version: NotRequired[str]
    entity_name: NotRequired[str]


def create_error_command(message: str, tool_call_id: str) -> Command:
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


def create_transition_command(
    message: str, tool_call_id: str, new_step: str, **updates: Any
) -> Command:
    """Create a Command for successful state transitions."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ],
            "current_step": new_step,
            **updates,
        }
    )
