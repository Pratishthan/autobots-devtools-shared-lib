# ABOUTME: Factory for the dynagent base agent.
# ABOUTME: Assembles model, middleware stack, and tool set into a runnable agent.

from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from autobots_devtools_shared_lib.common.observability import get_agent_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.middleware import (
    inject_agent_async,
    inject_agent_sync,
)
from autobots_devtools_shared_lib.dynagent.llm.llm import lm
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_all_tools

logger = get_agent_logger(__name__)


def create_base_agent(
    checkpointer: Any = None, sync_mode: bool = False, initial_agent_name: str | None = None
) -> CompiledStateGraph:
    """Create the dynagent base agent with middleware.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
            Defaults to InMemorySaver.
        sync_mode: Whether to use synchronous middleware (for batch processing).
        agent_name: Name for tracing/observability. Defaults to "dynagent".

    Returns:
        Configured LangGraph agent.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Warm the singleton
    AgentMeta.instance()

    model = lm()

    # All registry tools — middleware controls which subset is active per agent
    all_tools = get_all_tools()

    _middleware = inject_agent_sync if sync_mode else inject_agent_async

    if initial_agent_name is None:
        initial_agent_name = get_default_agent()

    return create_agent(
        model,
        name=initial_agent_name or "dynagent",
        tools=all_tools,
        state_schema=Dynagent,
        middleware=cast(
            "list[AgentMiddleware[Any, Any]]",
            [
                _middleware,
                SummarizationMiddleware(
                    model=model,
                    trigger=("fraction", 0.6),
                    keep=("messages", 20),
                ),
            ],
        ),
        checkpointer=checkpointer,
    )
