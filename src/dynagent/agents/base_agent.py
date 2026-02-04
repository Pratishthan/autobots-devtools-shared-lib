# ABOUTME: Factory for the dynagent base agent.
# ABOUTME: Assembles model, middleware stack, and tool set into a runnable agent.

import logging
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from dynagent.agents.agent_meta import AgentMeta
from dynagent.agents.middleware import inject_agent
from dynagent.llm.llm import lm
from dynagent.models.state import Dynagent
from dynagent.tools.tool_registry import get_tools

logger = logging.getLogger(__name__)


def create_base_agent(checkpointer: Any = None):
    """Create the dynagent base agent with middleware.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
            Defaults to InMemorySaver.

    Returns:
        Configured LangGraph agent.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Warm the singleton
    AgentMeta.instance()

    model = lm()

    # All registry tools — middleware controls which subset is active per agent
    all_tools = get_tools()

    agent = create_agent(
        model,
        name="dynagent",
        tools=all_tools,
        state_schema=Dynagent,
        middleware=cast(
            list[AgentMiddleware[Any, Any]],
            [
                inject_agent,
                SummarizationMiddleware(
                    model=model,
                    trigger=("fraction", 0.6),
                    keep=("messages", 20),
                ),
            ],
        ),
        checkpointer=checkpointer,
    )

    return agent
