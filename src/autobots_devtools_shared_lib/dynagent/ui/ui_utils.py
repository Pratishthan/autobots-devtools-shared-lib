# ABOUTME: Shared streaming and rendering utilities for dynagent-based UIs.
# ABOUTME: No imports from any use-case package (e.g. bro_chat); safe for reuse.

import base64
import json
from collections import deque
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import chainlit as cl
import requests
from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes
from langgraph.graph.state import CompiledStateGraph

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.common.observability.tracing import (
    flush_tracing,
    get_langfuse_client,
    get_langfuse_handler,
)

logger = get_logger(__name__)


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


def _extract_token_fragments(chunk: Any) -> list[str]:
    """Return the ordered text fragments in a streamed chat-model chunk.

    Handles string content, a list of string / ``.text`` / ``{"text": ...}`` blocks,
    and returns ``[]`` for empty or content-less chunks.
    """
    content = getattr(chunk, "content", None)
    if not content:
        return []
    if isinstance(content, str):
        return [content]
    fragments: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                fragments.append(block)
            elif hasattr(block, "text"):
                fragments.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                fragments.append(block["text"])
    return fragments


# ---------------------------------------------------------------------------
# File upload helpers (requires Chainlit runtime)
# ---------------------------------------------------------------------------


async def _upload_file_to_server(
    file_name: str,
    file_content: bytes,
    session_id: str,
) -> dict[str, Any]:
    """Upload a file to the file server.

    The file server URL is derived from :class:`FileServerConfig` (host/port).

    Args:
        file_name: Original name of the file.
        file_content: Raw bytes content of the file.
        session_id: Chainlit session ID for collision avoidance.

    Returns:
        Response dict from the file server with path and metadata.
    """
    from autobots_devtools_shared_lib.common.servers.fileserver.config import FileServerConfig

    file_server_url = f"http://{FileServerConfig.host}:{FileServerConfig.port}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_session_id = session_id[:8]
    unique_filename = f"temp/{safe_session_id}_{timestamp}_{file_name}"

    base64_content = base64.b64encode(file_content).decode("utf-8")

    payload = {"file_name": unique_filename, "file_content": base64_content}

    response = requests.post(f"{file_server_url}/writeFile", json=payload, timeout=30)

    if response.status_code == 200:
        return response.json()

    logger.error(f"File server returned status {response.status_code}: {response.text}")
    raise RuntimeError(f"File server error: {response.status_code}")


async def _process_uploaded_files(
    user_message: cl.Message,
    thread_id: str,
) -> list[dict[str, Any]]:
    """Process uploaded files attached to a Chainlit message.

    Reads each file element, uploads it to the file server, and returns
    metadata for every successfully uploaded file.  Files are staged in a
    ``temp/`` directory on the file server — the **LLM agent** is responsible
    for moving them to the final location via ``move_file_tool``.

    The caller must verify that ``user_message`` has file elements before
    invoking this helper.

    Args:
        user_message: Chainlit ``Message`` containing file elements.
        thread_id: Session / thread ID used for collision-safe filenames.

    Returns:
        List of metadata dicts with keys ``original_name``, ``server_path``,
        ``size_bytes``, and ``uploaded_at``.
    """
    uploaded_files_metadata: list[dict[str, Any]] = []

    logger.info(f"Processing {len(user_message.elements)} uploaded file(s)")

    for element in user_message.elements:
        try:
            file_name = element.name
            file_path = element.path
            if not file_path:
                logger.warning(f"No file path for element '{file_name}', skipping")
                continue
            p = Path(file_path)
            file_size = p.stat().st_size if p.exists() else 0

            logger.info(f"Processing file: {file_name} ({file_size} bytes)")

            with p.open("rb") as f:
                file_content = f.read()

            try:
                upload_response = await _upload_file_to_server(file_name, file_content, thread_id)

                uploaded_files_metadata.append(
                    {
                        "original_name": file_name,
                        "server_path": upload_response.get("path"),
                        "size_bytes": upload_response.get("size_bytes", file_size),
                        "uploaded_at": datetime.now().isoformat(),
                    }
                )

                await cl.Message(
                    content=f"File '{file_name}' uploaded successfully ({file_size / 1024:.2f} KB)"
                ).send()

                logger.info(
                    f"File uploaded successfully: {file_name} -> {upload_response.get('path')}"
                )

            except Exception as upload_error:
                await cl.Message(content=f"Failed to upload '{file_name}': {upload_error}").send()
                logger.exception(f"Upload error for {file_name}")
                continue

        except Exception as e:
            await cl.Message(content=f"Error processing file '{element.name}': {e}").send()
            logger.exception(f"File processing error for {element.name}")
            continue

    return uploaded_files_metadata


def _enrich_text_with_file_metadata(
    text_input: str, uploaded_files_metadata: list[dict[str, Any]]
) -> str:
    """Append uploaded file metadata to the user's text input.

    Args:
        text_input: Original user message text.
        uploaded_files_metadata: List returned by :func:`_process_uploaded_files`.

    Returns:
        Enriched text with file paths appended, or the original text if no files.
    """
    if not uploaded_files_metadata:
        return text_input

    file_info = "\n".join(
        f"- {f['original_name']} (Path: {f['server_path']})" for f in uploaded_files_metadata
    )
    upload_files_meta = f"{text_input}\n\n[Uploaded files:\n{file_info}]"
    logger.info(f"Files Meta: {upload_files_meta}")
    return upload_files_meta


# ---------------------------------------------------------------------------
# Async streaming helper (requires Chainlit runtime)
# ---------------------------------------------------------------------------


async def stream_agent_events(
    agent: CompiledStateGraph,
    input_state: dict[str, Any],
    config: RunnableConfig,
    on_structured_output: Callable[[dict[str, Any], str | None], str] | None = None,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
    user_message: cl.Message | None = None,
) -> None:
    """Stream events from a LangGraph agent and render them in Chainlit.

    Handles token streaming, collapsible tool steps, and structured-output
    messages.  When *on_structured_output* is provided it is called with
    ``(structured_dict, output_type)`` to produce the markdown body; otherwise
    :func:`structured_to_markdown` is used as the fallback.

    When *user_message* is provided and contains file elements, uploaded files
    are uploaded to the file server and their paths are appended to the
    first user message in *input_state*.  Files are staged in ``temp/`` —
    the LLM agent moves them to the final location via ``move_file_tool``.

    Args:
        agent: A LangGraph ``Runnable`` that supports ``astream_events``.
        input_state: The ``{"messages": …}`` dict (plus any extra state keys)
            passed to the agent.
        config: LangChain ``RunnableConfig`` (thread_id, callbacks, etc.).
        on_structured_output: Optional formatter callback.  Signature:
            ``(data: dict, output_type: str | None) -> str``.
        enable_tracing: Whether to enable Langfuse tracing (default True, gracefully
            degrades if not configured).
        trace_metadata: Optional TraceMetadata instance with session_id, app_name,
            user_id, and tags. If None, uses defaults.
        user_message: Optional raw Chainlit ``Message``. When supplied, any attached
            file elements are uploaded to the file server and their paths are
            appended to the user's text input.
    """
    # --- Process file uploads if user_message has attachments ---------------
    if user_message is not None and hasattr(user_message, "elements") and user_message.elements:
        thread_id = input_state.get("session_id", "default")
        uploaded_files = await _process_uploaded_files(user_message, thread_id)
        if uploaded_files:
            # Enrich the first user message content with file metadata
            messages = input_state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                original_content = (
                    last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
                )
                enriched = _enrich_text_with_file_metadata(original_content, uploaded_files)
                if isinstance(last_msg, dict):
                    last_msg["content"] = enriched

    # Use provided metadata or create default
    if trace_metadata is None:
        trace_metadata = TraceMetadata.create()
        if "session_id" in input_state:
            trace_metadata.session_id = input_state["session_id"]

    # Ensure input_state has session_id for agent context
    if "session_id" not in input_state:
        input_state["session_id"] = trace_metadata.session_id

    # Auto-create Langfuse handler if tracing enabled and not already in config callbacks
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

    # --- Execute with observability wrapper ---
    try:
        client = get_langfuse_client() if enable_tracing else None

        with propagate_attributes(
            user_id=trace_metadata.user_id,
            session_id=trace_metadata.session_id,
            tags=trace_metadata.tags,
        ):
            span_ctx = (
                client.start_as_current_observation(
                    as_type="span",
                    name=f"{trace_metadata.app_name}-stream",
                    input={
                        "message_count": len(input_state.get("messages", [])),
                    },
                    metadata=trace_metadata.to_dict(),
                )
                if client is not None
                else nullcontext()
            )
            with span_ctx as span:
                msg = cl.Message(content="")
                tool_steps: dict[str, cl.Step] = {}
                tool_step_queue: deque[str] = deque(maxlen=3)
                structured_response_count = 0

                await msg.send()

                async for event in agent.astream_events(
                    input_state,
                    config=RunnableConfig(**config),
                    version="v2",
                ):
                    kind = event["event"]

                    # --- token streaming ----------------------------------------------
                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        content = chunk.content if chunk and hasattr(chunk, "content") else None
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
                                    structured_response_count += 1
                                    structured_dict: dict[str, Any]
                                    if is_dataclass(structured) and not isinstance(
                                        structured, type
                                    ):
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
                                    output_type = (
                                        _extract_output_type(current_step) if current_step else None
                                    )

                                    # Convert to Markdown
                                    if on_structured_output:
                                        markdown = on_structured_output(
                                            structured_dict, output_type
                                        )
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

                # Update span with results
                if span is not None:
                    span.update(
                        output={
                            "structured_responses": structured_response_count,
                            "message_length": len(msg.content) if msg.content else 0,
                        }
                    )
    finally:
        if enable_tracing:
            flush_tracing()
