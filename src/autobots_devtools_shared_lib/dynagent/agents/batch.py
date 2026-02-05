# ABOUTME: Batch processing interface for the dynagent layer.
# ABOUTME: Wraps prompts into parallel agent invocations with per-record results.

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

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


def _build_configs(count: int) -> list[RunnableConfig]:
    """Build a list of RunnableConfigs, each with a unique thread_id.

    MUST be a list — broadcasting a single config causes all items to share
    one checkpointer thread, corrupting state.
    """
    return [{"configurable": {"thread_id": str(uuid.uuid4())}} for _ in range(count)]


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


def batch_invoker(agent_name: str, records: list[str]) -> BatchResult:
    """Run a list of prompts through the dynagent in parallel.

    Args:
        agent_name: Name of the agent to invoke (must exist in agents.yaml).
        records: Non-empty list of plain-string prompts.

    Returns:
        BatchResult with per-record success/failure details.

    Raises:
        ValueError: If agent_name is unknown or records is empty.
    """
    # --- Validation (same source as _validate_handoff in state_tools) ---
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
        get_agent_list,
    )

    valid_agents = get_agent_list()
    if agent_name not in valid_agents:
        raise ValueError(
            f"Unknown agent: {agent_name}. Valid agents: {', '.join(valid_agents)}"
        )
    if not records:
        raise ValueError("records must not be empty")

    # --- Agent creation ---
    from langgraph.checkpoint.memory import InMemorySaver

    from autobots_devtools_shared_lib.dynagent.agents.base_agent import (
        create_base_agent,
    )

    agent = create_base_agent(checkpointer=InMemorySaver(), sync_mode=True)

    # --- Build inputs & configs ---
    inputs = _build_inputs(agent_name, records)
    configs = _build_configs(len(records))

    # --- Execute in parallel (thread pool via .batch) ---
    # return_exceptions=True captures per-record failures instead of aborting.
    raw_outputs: list[Any] = agent.batch(inputs, config=configs, return_exceptions=True)

    # --- Wrap raw outputs into BatchResult ---
    results: list[RecordResult] = []
    for idx, output in enumerate(raw_outputs):
        if isinstance(output, BaseException):
            results.append(RecordResult(index=idx, success=False, error=str(output)))
        else:
            content = _extract_last_ai_content(output)
            results.append(RecordResult(index=idx, success=True, output=content))

    return BatchResult(agent_name=agent_name, total=len(records), results=results)


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
