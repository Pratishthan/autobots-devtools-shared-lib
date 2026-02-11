# ABOUTME: Batch processing interface for the dynagent layer.
# ABOUTME: Wraps prompts into parallel agent invocations with per-record results.

import logging
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes

from autobots_devtools_shared_lib.common.observability.tracing import (
    flush_tracing,
    get_langfuse_client,
    get_langfuse_handler,
)

logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Result types (co-located dataclasses — same pattern as AgentConfig)
# ---------------------------------------------------------------------------


@dataclass
class RecordResult:
    """Outcome for a single record in a batch run."""

    index: int
    success: bool
    output: str | None = None
    error: str | None = None


@dataclass
class BatchResult:
    """Aggregate result of a batch run."""

    agent_name: str
    total: int
    results: list[RecordResult] = field(default_factory=list)

    @property
    def successes(self) -> list[RecordResult]:
        """Records that completed without error."""
        return [r for r in self.results if r.success]

    @property
    def failures(self) -> list[RecordResult]:
        """Records that raised an exception."""
        return [r for r in self.results if not r.success]


# ---------------------------------------------------------------------------
# Private helpers (tested directly — same split-pattern as state_tools.py)
# ---------------------------------------------------------------------------


def _build_inputs(agent_name: str, records: list[str]) -> list[dict[str, Any]]:
    """Convert plain-string records into agent input-state dicts.

    Each input gets a uuid4 session_id for workspace isolation.
    """
    return [
        {
            "messages": [{"role": "user", "content": record}],
            "agent_name": agent_name,
            "session_id": str(uuid.uuid4()),
        }
        for record in records
    ]


def _build_configs(
    count: int, callbacks: list[Any] | None = None, max_concurrency: int = 1
) -> list[RunnableConfig]:
    """Build a list of RunnableConfigs, each with a unique thread_id.

    Args:
        count: Number of configs to build.
        callbacks: Optional list of callback handlers to inject into each config.
    """
    configs: list[RunnableConfig] = []
    for _ in range(count):
        config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}
        if callbacks:
            config["callbacks"] = callbacks
        config["max_concurrency"] = max_concurrency
        configs.append(config)
    return configs


def _extract_last_ai_content(state_output: dict[str, Any]) -> str | None:
    """Extract the final AI message content from an agent output state.

    Handles both dict messages ({"role": "ai", ...}) and BaseMessage objects
    (msg.type == "ai", msg.content), since LangGraph returns either depending
    on the code path.  The 'assistant' role alias is recognised for dict messages.
    """
    messages = state_output.get("messages")
    if not messages:
        return None

    # Walk in reverse to find the last AI message
    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("role") in ("ai", "assistant"):
                return msg.get("content")  # type: ignore[return-value]
        else:
            # BaseMessage-style object
            if getattr(msg, "type", None) == "ai":
                return getattr(msg, "content", None)  # type: ignore[return-value]

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def batch_invoker(
    agent_name: str,
    records: list[str],
    callbacks: list[Any] | None = None,
    enable_tracing: bool = True,
    batch_id: str | None = None,
    trace_metadata: dict[str, Any] | None = None,
) -> BatchResult:
    """Run a list of prompts through the dynagent in parallel.

    Args:
        agent_name: Name of the agent to invoke (must exist in agents.yaml).
        records: Non-empty list of plain-string prompts.
        callbacks: Optional list of callback handlers (e.g., Langfuse) for tracing.
        enable_tracing: Whether to enable Langfuse tracing (default True, gracefully
            degrades if not configured).
        batch_id: Optional batch ID for correlation (auto-generated if None).
        trace_metadata: Optional metadata dict with keys: app_name, user_id, tags, etc.
            Defaults: app_name="batch_invoker", user_id=agent_name, tags=[].

    Returns:
        BatchResult with per-record success/failure details.

    Raises:
        ValueError: If agent_name is unknown or records is empty.
    """
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
        get_agent_list,
        load_agents_config,
    )

    valid_agents = get_agent_list()

    if agent_name not in valid_agents:
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {', '.join(valid_agents)}")
    if not records:
        raise ValueError("records must not be empty")

    if batch_id is None:
        batch_id = str(uuid.uuid4())

    agent_cfg = load_agents_config()[agent_name]
    max_concurrency: int = (
        agent_cfg.max_concurrency
        if agent_cfg.max_concurrency and agent_cfg.max_concurrency > 0
        else 1
    )

    # Auto-create Langfuse handler if tracing enabled and no callbacks provided
    if enable_tracing and callbacks is None:
        langfuse_handler = get_langfuse_handler()
        if langfuse_handler:
            callbacks = [langfuse_handler]

    # Extract metadata with defaults
    app_name = (
        trace_metadata.get("app_name", "batch_invoker") if trace_metadata else "batch_invoker"
    )
    user_id = trace_metadata.get("user_id", agent_name) if trace_metadata else agent_name
    tags = trace_metadata.get("tags", []) if trace_metadata else []

    # --- Execute with observability wrapper ---
    try:
        client = get_langfuse_client() if enable_tracing else None

        with propagate_attributes(
            user_id=user_id,
            session_id=batch_id,
            tags=tags,
        ):
            span_ctx = (
                client.start_as_current_span(
                    name=f"{app_name}-{agent_name}-batch",
                    input={
                        "agent_name": agent_name,
                        "record_count": len(records),
                    },
                    metadata={"batch_id": batch_id, **(trace_metadata or {})},
                )
                if client is not None
                else nullcontext()
            )
            with span_ctx as span:
                # --- Agent creation ---
                from langgraph.checkpoint.memory import InMemorySaver

                from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
                    create_base_agent,
                )

                agent = create_base_agent(
                    checkpointer=InMemorySaver(), sync_mode=True, agent_name=agent_name
                )

                # --- Build inputs & configs ---
                inputs = _build_inputs(agent_name, records)

                configs = _build_configs(
                    len(records), callbacks=callbacks, max_concurrency=max_concurrency
                )

                # --- Execute in parallel (thread pool via .batch) ---
                # return_exceptions=True captures per-record failures
                # instead of aborting.
                raw_outputs: list[Any] = agent.batch(
                    inputs,
                    config=configs,
                    return_exceptions=True,
                )

                # --- Wrap raw outputs into BatchResult ---
                results: list[RecordResult] = []
                for idx, output in enumerate(raw_outputs):
                    if isinstance(output, BaseException):
                        results.append(RecordResult(index=idx, success=False, error=str(output)))
                    else:
                        content = _extract_last_ai_content(output)
                        results.append(RecordResult(index=idx, success=True, output=content))

                result = BatchResult(agent_name=agent_name, total=len(records), results=results)

                # Update span with results
                if span is not None:
                    span.update(
                        output={
                            "total": len(records),
                            "successes": len(result.successes),
                            "failures": len(result.failures),
                        }
                    )

                return result
    finally:
        if enable_tracing:
            flush_tracing()


if __name__ == "__main__":
    # Simple manual test
    test_prompts = [
        "Explain the significance of the Turing Test.",
        "What is the capital of France?",
        "Tell me a joke about computers.",
    ]
    batch_result = batch_invoker("coordinator", test_prompts)
    for record in batch_result.results:
        if record.success:
            print(f"Record {record.index} succeeded with output:\n{record.output}\n")
        else:
            print(f"Record {record.index} failed with error:\n{record.error}\n")
