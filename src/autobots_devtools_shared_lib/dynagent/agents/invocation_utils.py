# ABOUTME: Agent invocation utilities for orchestration workflows.
# ABOUTME: Provides sync/async wrappers with observability (no UI dependencies).

from contextlib import nullcontext
from typing import Any

from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.common.observability.tracing import (
    flush_tracing,
    get_langfuse_client,
    get_langfuse_handler,
)

logger = get_logger(__name__)


def invoke_agent(
    agent_name: str,
    input_state: dict[str, Any],
    config: RunnableConfig,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
) -> dict[str, Any]:
    """Synchronously invoke a LangGraph agent with observability support.

    Provides a simple wrapper around agent.invoke() with Langfuse tracing,
    session management, and proper error handling. Designed for orchestration
    workflows where agents are invoked programmatically (no UI rendering).

    Args:
        agent_name: Name of the agent to invoke (must exist in agents.yaml).
        input_state: Input state dict (must include "messages" key at minimum).
        config: LangChain RunnableConfig (thread_id, callbacks, etc.).
        enable_tracing: Whether to enable Langfuse tracing (default True,
            gracefully degrades if not configured).
        trace_metadata: Optional TraceMetadata with session_id, app_name,
            user_id, and tags. If None, uses defaults.

    Returns:
        The complete final state dict from the agent execution, including:
        - "messages": List of message objects
        - "structured_response": Structured output (if agent produced one)
        - Any other state keys the agent maintains

    Raises:
        ValueError: If agent_name is unknown.

    Example:
        >>> result = invoke_agent(
        ...     agent_name="joke_agent",
        ...     input_state={"messages": [{"role": "user", "content": "Tell me a joke"}]},
        ...     config={"configurable": {"thread_id": "test-123"}},
        ... )
        >>> print(result["structured_response"])
    """
    # Validate agent exists
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_agent_list

    valid_agents = get_agent_list()
    if agent_name not in valid_agents:
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {', '.join(valid_agents)}")
    # Use provided metadata or create default
    if trace_metadata is None:
        trace_metadata = TraceMetadata.create(
            app_name=f"{agent_name}-invoke",
        )
        if "session_id" in input_state:
            trace_metadata.session_id = input_state["session_id"]

    # Ensure input_state has session_id and agent_name for agent context
    if "session_id" not in input_state:
        input_state["session_id"] = trace_metadata.session_id
    if "agent_name" not in input_state:
        input_state["agent_name"] = agent_name

    # Auto-create Langfuse handler if tracing enabled
    if enable_tracing:
        langfuse_handler = get_langfuse_handler()

        if langfuse_handler:
            existing_callbacks = config.get("callbacks")

            if existing_callbacks is None:
                config["callbacks"] = [langfuse_handler]
            elif (
                isinstance(existing_callbacks, list) and langfuse_handler not in existing_callbacks
            ):
                config["callbacks"] = [*existing_callbacks, langfuse_handler]

    # Execute with observability wrapper
    try:
        client = get_langfuse_client() if enable_tracing else None

        with propagate_attributes(
            user_id=trace_metadata.user_id,
            session_id=trace_metadata.session_id,
            tags=trace_metadata.tags,
        ):
            span_ctx = (
                client.start_as_current_span(
                    name=f"{trace_metadata.app_name}-{agent_name}",
                    input={
                        "agent_name": agent_name,
                        "message_count": len(input_state.get("messages", [])),
                    },
                    metadata=trace_metadata.to_dict(),
                )
                if client is not None
                else nullcontext()
            )

            with span_ctx as span:
                # Create agent
                from langgraph.checkpoint.memory import InMemorySaver

                from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
                    create_base_agent,
                )

                agent = create_base_agent(
                    checkpointer=InMemorySaver(), sync_mode=True, initial_agent_name=agent_name
                )

                logger.info(
                    f"Invoking agent '{agent_name}' (sync) with session_id={trace_metadata.session_id}"
                )
                result = agent.invoke(input_state, config=config)

                # Update span with results
                if span is not None:
                    has_structured = "structured_response" in result
                    span.update(
                        output={
                            "has_structured_response": has_structured,
                            "final_message_count": len(result.get("messages", [])),
                        }
                    )

                logger.info(
                    f"Agent invocation complete. Has structured response: "
                    f"{'structured_response' in result}"
                )
                return result

    finally:
        if enable_tracing:
            flush_tracing()


async def ainvoke_agent(
    agent_name: str,
    input_state: dict[str, Any],
    config: RunnableConfig,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
) -> dict[str, Any]:
    """Asynchronously invoke a LangGraph agent with observability support.

    Async version of invoke_agent(). Provides a simple wrapper around
    agent.ainvoke() with Langfuse tracing, session management, and proper
    error handling. Designed for orchestration workflows where agents are
    invoked programmatically (no UI rendering).

    Args:
        agent_name: Name of the agent to invoke (must exist in agents.yaml).
        input_state: Input state dict (must include "messages" key at minimum).
        config: LangChain RunnableConfig (thread_id, callbacks, etc.).
        enable_tracing: Whether to enable Langfuse tracing (default True,
            gracefully degrades if not configured).
        trace_metadata: Optional TraceMetadata with session_id, app_name,
            user_id, and tags. If None, uses defaults.

    Returns:
        The complete final state dict from the agent execution, including:
        - "messages": List of message objects
        - "structured_response": Structured output (if agent produced one)
        - Any other state keys the agent maintains

    Raises:
        ValueError: If agent_name is unknown.

    Example:
        >>> result = await ainvoke_agent(
        ...     agent_name="joke_agent",
        ...     input_state={"messages": [{"role": "user", "content": "Tell me a joke"}]},
        ...     config={"configurable": {"thread_id": "test-123"}},
        ... )
        >>> print(result["structured_response"])
    """
    # Validate agent exists
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_agent_list

    valid_agents = get_agent_list()
    if agent_name not in valid_agents:
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {', '.join(valid_agents)}")
    # Use provided metadata or create default
    if trace_metadata is None:
        trace_metadata = TraceMetadata.create(
            app_name=f"{agent_name}-ainvoke",
        )
        if "session_id" in input_state:
            trace_metadata.session_id = input_state["session_id"]

    # Ensure input_state has session_id and agent_name for agent context
    if "session_id" not in input_state:
        input_state["session_id"] = trace_metadata.session_id
    if "agent_name" not in input_state:
        input_state["agent_name"] = agent_name

    # Auto-create Langfuse handler if tracing enabled
    if enable_tracing:
        langfuse_handler = get_langfuse_handler()

        if langfuse_handler:
            existing_callbacks = config.get("callbacks")

            if existing_callbacks is None:
                config["callbacks"] = [langfuse_handler]
            elif (
                isinstance(existing_callbacks, list) and langfuse_handler not in existing_callbacks
            ):
                config["callbacks"] = [*existing_callbacks, langfuse_handler]

    # Execute with observability wrapper
    try:
        client = get_langfuse_client() if enable_tracing else None

        with propagate_attributes(
            user_id=trace_metadata.user_id,
            session_id=trace_metadata.session_id,
            tags=trace_metadata.tags,
        ):
            span_ctx = (
                client.start_as_current_span(
                    name=f"{trace_metadata.app_name}-{agent_name}",
                    input={
                        "agent_name": agent_name,
                        "message_count": len(input_state.get("messages", [])),
                    },
                    metadata=trace_metadata.to_dict(),
                )
                if client is not None
                else nullcontext()
            )

            with span_ctx as span:
                # Create agent
                from langgraph.checkpoint.memory import InMemorySaver

                from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
                    create_base_agent,
                )

                agent = create_base_agent(
                    checkpointer=InMemorySaver(), sync_mode=False, initial_agent_name=agent_name
                )

                logger.info(
                    f"Invoking agent '{agent_name}' (async) with session_id={trace_metadata.session_id}"
                )
                result = await agent.ainvoke(input_state, config=config)

                # Update span with results
                if span is not None:
                    has_structured = "structured_response" in result
                    span.update(
                        output={
                            "has_structured_response": has_structured,
                            "final_message_count": len(result.get("messages", [])),
                        }
                    )

                logger.info(
                    f"Agent invocation complete. Has structured response: "
                    f"{'structured_response' in result}"
                )
                return result

    finally:
        if enable_tracing:
            flush_tracing()
