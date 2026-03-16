# ABOUTME: Agent invocation utilities for orchestration workflows.
# ABOUTME: Provides sync/async wrappers with observability (no UI dependencies).

import json
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware.types import ResponseT
from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.common.observability.trace_propagation import otel_span
from autobots_devtools_shared_lib.common.observability.tracing import (
    flush_tracing,
    get_langfuse_handler,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

logger = get_logger(__name__)


def _format_otel_trace_id(trace_id: int) -> str:
    """Convert OTel int trace_id to 32-char hex string for Langfuse CallbackHandler."""
    return format(trace_id, "032x")


def _linked_langfuse_handler(otel_span: Any) -> Any:
    """Build a Langfuse CallbackHandler linked to the current OTel trace.

    When an active OTel span is given, pins trace_id so LLM sub-spans (token
    counts, prompt/completions) nest under the same Langfuse trace as the
    http.client.* file-server spans.  Falls back to the default handler when
    OTel is unavailable.
    """
    try:
        if otel_span is not None:
            ctx = otel_span.get_span_context()
            if ctx.is_valid:
                from langfuse.langchain import CallbackHandler

                return CallbackHandler(
                    trace_context={
                        "trace_id": _format_otel_trace_id(ctx.trace_id),
                        "parent_span_id": format(ctx.span_id, "016x"),
                    },
                )
    except Exception:
        logger.debug(
            "Failed to build linked Langfuse handler; falling back to default", exc_info=True
        )
    return get_langfuse_handler()


def inject_langfuse_handler_into_config(
    config: RunnableConfig | None,
    langfuse_handler: Any,
) -> RunnableConfig:
    """Inject Langfuse handler into config callbacks. Returns config (mutates when not None)."""
    if langfuse_handler is None:
        return config if config is not None else {}
    if config is None:
        return {"callbacks": [langfuse_handler]}
    existing = config.get("callbacks")
    if isinstance(existing, list):
        config["callbacks"] = [*existing, langfuse_handler]
    else:
        config["callbacks"] = [langfuse_handler]
    return config


def invoke_agent(
    agent_name: str,
    input_state: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    config: RunnableConfig | None = None,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
    state_schema: type[AgentState[ResponseT]] = Dynagent,
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
        state_schema: State schema for the agent. Defaults to Dynagent.
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

    if input_state is None:
        input_state = {}
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

    # Execute with observability wrapper
    try:
        with (
            propagate_attributes(
                user_id=trace_metadata.user_id,
                session_id=trace_metadata.session_id,
                tags=trace_metadata.tags,
            ),
            # OTel root span — sets the OTel context so traced_http_call() spans
            # (readFile/writeFile) become children of this span in Langfuse.
            otel_span(f"{trace_metadata.app_name}-{agent_name}") as span,
        ):
            if enable_tracing:
                config = inject_langfuse_handler_into_config(config, _linked_langfuse_handler(span))

            if span is not None:
                span.set_attribute("langfuse.session.id", str(trace_metadata.session_id))
                span.set_attribute(
                    "input.value",
                    json.dumps(
                        {
                            "agent_name": agent_name,
                            "message_count": len(input_state.get("messages", [])),
                        }
                    ),
                )

            # Create agent
            from langgraph.checkpoint.memory import InMemorySaver

            from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
                create_base_agent,
            )

            if checkpointer is None:
                checkpointer = InMemorySaver()

            agent = create_base_agent(
                checkpointer=checkpointer,
                state_schema=state_schema,
                sync_mode=True,
                initial_agent_name=agent_name,  # pyright: ignore[reportCallIssue]
            )

            logger.info(
                f"Invoking agent '{agent_name}' (sync) with session_id={trace_metadata.session_id}"
            )
            result = agent.invoke(input_state, config=config)

            if span is not None:
                span.set_attribute(
                    "output.value",
                    json.dumps(
                        {
                            "has_structured_response": "structured_response" in result,
                            "final_message_count": len(result.get("messages", [])),
                        }
                    ),
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
    input_state: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    config: RunnableConfig | None = None,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
    state_schema: type[AgentState[ResponseT]] = Dynagent,
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
        state_schema: State schema for the agent. Defaults to Dynagent.

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
    if input_state is None:
        input_state = {}
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

    # Execute with observability wrapper
    try:
        with (
            propagate_attributes(
                user_id=trace_metadata.user_id,
                session_id=trace_metadata.session_id,
                tags=trace_metadata.tags,
            ),
            # OTel root span — sets the OTel context so traced_http_call() spans
            # (readFile/writeFile) become children of this span in Langfuse.
            otel_span(f"{trace_metadata.app_name}-{agent_name}") as span,
        ):
            if enable_tracing:
                config = inject_langfuse_handler_into_config(config, _linked_langfuse_handler(span))

            if span is not None:
                span.set_attribute("langfuse.session.id", str(trace_metadata.session_id))
                span.set_attribute(
                    "input.value",
                    json.dumps(
                        {
                            "agent_name": agent_name,
                            "message_count": len(input_state.get("messages", [])),
                        }
                    ),
                )

            # Create agent
            from langgraph.checkpoint.memory import InMemorySaver

            from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
                create_base_agent,
            )

            if checkpointer is None:
                checkpointer = InMemorySaver()

            agent = create_base_agent(
                checkpointer=checkpointer,
                state_schema=state_schema,
                sync_mode=False,
                initial_agent_name=agent_name,  # pyright: ignore[reportCallIssue]
            )

            logger.info(
                f"Invoking agent '{agent_name}' (async) with session_id={trace_metadata.session_id}"
            )
            result = await agent.ainvoke(input_state, config=config)

            if span is not None:
                span.set_attribute(
                    "output.value",
                    json.dumps(
                        {
                            "has_structured_response": "structured_response" in result,
                            "final_message_count": len(result.get("messages", [])),
                        }
                    ),
                )

            logger.info(
                f"Agent invocation complete. Has structured response: "
                f"{'structured_response' in result}"
            )
            return result

    finally:
        if enable_tracing:
            flush_tracing()
