# ABOUTME: Service for converting conversation history to structured output.
# ABOUTME: Filters messages by agent and uses LLM to extract structured data.

import json
from collections.abc import Sequence
from typing import Any

from langchain.messages import ToolMessage
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.config.settings import get_settings

logger = get_logger(__name__)


class StructuredOutputConverter:
    """Convert conversation history to structured output using LLM."""

    def __init__(self, model: ChatGoogleGenerativeAI):
        """Initialize with LLM model for conversion.

        Args:
            model: ChatGoogleGenerativeAI instance to use for conversion.
        """
        self.model = model

    def _filter_messages_for_agent(
        self, messages: Sequence[BaseMessage], current_agent: str
    ) -> Sequence[BaseMessage]:
        """Extract only messages since current agent took over.

        Logic:
        1. Iterate backwards through messages
        2. Look for ToolMessage indicating handoff to current_agent
        3. Return all messages after that handoff
        4. If no handoff found, return all messages (coordinator case)

        Args:
            messages: Full conversation history.
            current_agent: Current agent name to filter for.

        Returns:
            Filtered list of messages for current agent.
        """
        # Find the last handoff to current_agent
        handoff_index = None
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            handoff_text = f"Handoff to {current_agent}"
            if isinstance(msg, ToolMessage) and handoff_text in msg.content:
                handoff_index = i
                break

        # Return messages after handoff (or all if no handoff)
        if handoff_index is not None:
            return messages[handoff_index + 1 :]
        return messages  # Coordinator or first agent

    def _create_conversion_prompt(self, messages: Sequence[BaseMessage]) -> str:
        """Create prompt for LLM to convert conversation to structured data.

        Args:
            messages: Filtered conversation messages.

        Returns:
            Formatted prompt string.
        """
        # Format conversation history
        conversation_lines = []
        for msg in messages:
            if hasattr(msg, "type"):
                msg_type = msg.type
                content = msg.content if hasattr(msg, "content") else str(msg)
                conversation_lines.append(f"{msg_type.upper()}: {content}")

        conversation_history = "\n".join(conversation_lines)

        return (
            "Based on the conversation history below, create a comprehensive "
            "structured summary.\n"
            "Extract all relevant information and ensure all required fields "
            "are populated.\n\n"
            "If any required information is missing from the conversation, you "
            "should still provide your best attempt at extracting what is "
            "available.\n\n"
            f"Conversation:\n{conversation_history}\n"
        )

    def convert(
        self, messages: Sequence[BaseMessage], schema_path: str, current_agent: str
    ) -> tuple[Any | None, str | None]:
        """Convert messages to structured output.

        Args:
            messages: Conversation history to convert.
            schema_path: Path to JSON schema (e.g., "vision-agent/01-preface.json").
            current_agent: Current agent name for filtering messages.

        Returns:
            (dict with structured data, None) on success
            (None, error_message) on failure
        """
        # Filter messages to current agent's conversation (cheap check first)
        filtered_messages = self._filter_messages_for_agent(messages, current_agent)
        if not filtered_messages:
            error_msg = "No conversation history found for current agent"
            logger.warning(error_msg)
            return None, error_msg

        # Load JSON schema from file
        schema_file = get_settings().dynagent_config_root_dir / "schemas" / schema_path
        if not schema_file.exists():
            error_msg = f"Schema file not found: {schema_file}"
            logger.error(error_msg)
            return None, error_msg

        try:
            with schema_file.open() as f:
                json_schema = json.load(f)
        except Exception as e:
            error_msg = f"Failed to load schema file {schema_file}: {e!s}"
            logger.exception(error_msg)
            return None, error_msg

        # Create conversion prompt
        conversion_prompt = self._create_conversion_prompt(filtered_messages)

        # Use structured output to convert
        try:
            schema_title = json_schema.get("title", schema_path)
            logger.info(f"Converting conversation to {schema_title} for agent {current_agent}")
            structured_llm = self.model.with_structured_output(json_schema, method="json_schema")
            result = structured_llm.invoke(conversion_prompt)

        except Exception as e:
            error_msg = f"Failed to convert conversation to structured output: {e!s}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
        else:
            logger.info(f"Successfully converted to structured output: {schema_title}")
            return result, None
