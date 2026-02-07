# ABOUTME: Shared streaming and rendering utilities for dynagent-based UIs.
# ABOUTME: No imports from any use-case package (e.g. bro_chat); safe for reuse.

import json
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

import chainlit as cl
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure formatting helpers (no Chainlit dependency)
# ---------------------------------------------------------------------------


def structured_to_markdown(data: dict[str, Any], title: str = "Response") -> str:
    """Convert a structured output dict to readable Markdown.

    Args:
        data: Structured response from agent (dict from dataclass)
        title: Section title for the markdown output

    Returns:
        Formatted markdown string
    """
    lines = [f"## {title}\n"]

    for key, value in data.items():
        # Convert snake_case to Title Case
        display_key = key.replace("_", " ").title()

        if isinstance(value, list):
            lines.append(f"**{display_key}:**\n")
            for item in value:
                if isinstance(item, dict):
                    # Nested object (e.g., FeatureItem)
                    lines.append(format_dict_item(item))
                else:
                    # Simple list item
                    lines.append(f"- {item}")
            lines.append("")  # Blank line

        elif isinstance(value, dict):
            # Nested object
            lines.append(f"**{display_key}:**\n")
            lines.append(format_dict_item(value))
            lines.append("")

        else:
            # Simple value (string, number, bool)
            lines.append(f"**{display_key}:** {value}\n")

    return "\n".join(lines)


def format_dict_item(item: dict[str, Any], indent: int = 0) -> str:
    """Format a dictionary item as indented key-value pairs."""
    lines = []
    prefix = "  " * indent

    for k, v in item.items():
        display_k = k.replace("_", " ").title()
        if isinstance(v, dict):
            lines.append(f"{prefix}- **{display_k}:**")
            lines.append(format_dict_item(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}- **{display_k}:** {', '.join(str(x) for x in v)}")
        else:
            lines.append(f"{prefix}- **{display_k}:** {v}")

    return "\n".join(lines)


def _extract_output_type(step_name: str | None) -> str | None:
    """Extract output type from step name (e.g., 'features_agent' -> 'features')."""
    if not step_name:
        return None
    return step_name.replace("_agent", "").replace("_", "")


# ---------------------------------------------------------------------------
# Async streaming helper (requires Chainlit runtime)
# ---------------------------------------------------------------------------


async def stream_agent_events(
    agent: Any,
    input_state: dict[str, Any],
    config: RunnableConfig,
    on_structured_output: Callable[[dict[str, Any], str | None], str] | None = None,
) -> None:
    """Stream events from a LangGraph agent and render them in Chainlit.

    Handles token streaming, collapsible tool steps, and structured-output
    messages.  When *on_structured_output* is provided it is called with
    ``(structured_dict, output_type)`` to produce the markdown body; otherwise
    :func:`structured_to_markdown` is used as the fallback.

    Args:
        agent: A LangGraph ``Runnable`` that supports ``astream_events``.
        input_state: The ``{"messages": …}`` dict (plus any extra state keys)
            passed to the agent.
        config: LangChain ``RunnableConfig`` (thread_id, callbacks, etc.).
        on_structured_output: Optional formatter callback.  Signature:
            ``(data: dict, output_type: str | None) -> str``.
    """
    msg = cl.Message(content="")
    tool_steps: dict[str, cl.Step] = {}
    tool_step_queue: deque[str] = deque(maxlen=3)

    await msg.send()

    async for event in agent.astream_events(
        input_state,
        config=RunnableConfig(**config),
        version="v2",
    ):
        kind = event["event"]

        # --- token streaming ----------------------------------------------
        if kind == "on_chat_model_stream":
            content = event.get("data", {}).get("chunk", {}).content
            if content:
                # Handle content as list or string
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, str):
                            await msg.stream_token(block)
                        elif hasattr(block, "text"):
                            await msg.stream_token(block.text)
                        elif isinstance(block, dict) and "text" in block:
                            await msg.stream_token(block["text"])
                else:
                    await msg.stream_token(content)

        # --- tool start ----------------------------------------------------
        elif kind == "on_tool_start":
            tool_name = event.get("name", "unknown")
            tool_input = event["data"].get("input", {})
            run_id = event.get("run_id")

            # Remove oldest step if we're at max capacity
            if len(tool_step_queue) >= 3:
                old_run_id = tool_step_queue.popleft()
                if old_run_id in tool_steps:
                    old_step = tool_steps[old_run_id]
                    await old_step.remove()
                    del tool_steps[old_run_id]

            async with cl.Step(name=f"🛠️ {tool_name}", type="tool") as step:
                step.input = tool_input
                tool_steps[run_id] = step
                tool_step_queue.append(run_id)

        # --- tool end ------------------------------------------------------
        elif kind == "on_tool_end":
            run_id = event.get("run_id")
            output = event["data"].get("output", "")

            if run_id in tool_steps:
                step = tool_steps[run_id]
                step.output = str(output)[:1000]  # Limit output length
                await step.update()

        # --- chain end (structured output) ---------------------------------
        elif kind == "on_chain_end":
            data = event.get("data", {})
            output = data.get("output", {})

            if output:
                if isinstance(output, dict):
                    structured = output.get("structured_response", None)
                    if structured:
                        structured_dict: dict[str, Any]
                        if is_dataclass(structured) and not isinstance(structured, type):
                            structured_dict = asdict(structured)
                        elif isinstance(structured, dict):
                            structured_dict = structured
                        else:
                            # Fallback: skip if not dict or dataclass
                            logger.warning(
                                f"Unexpected structured response type: {type(structured)}"
                            )
                            continue

                        # Log JSON for debugging
                        json_str = json.dumps(structured_dict, indent=2)
                        logger.info(f"Structured response (JSON): {json_str}")

                        # Extract output type from agent_name if available
                        current_step = output.get("agent_name")
                        output_type = _extract_output_type(current_step) if current_step else None

                        # Convert to Markdown
                        if on_structured_output:
                            markdown = on_structured_output(structured_dict, output_type)
                        else:
                            markdown = structured_to_markdown(structured_dict)

                        # Send as a separate message for clean formatting
                        await cl.Message(content=markdown, author="Assistant").send()
                    else:
                        logger.debug("No structured response found in output.")
                elif isinstance(output, list):
                    # Iterate through list items
                    for item in output:
                        logger.info(f"Output item: {item}")
            else:
                logger.warning("No output found in chain end event.")

    await msg.update()
