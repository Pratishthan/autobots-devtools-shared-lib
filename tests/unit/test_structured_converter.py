# ABOUTME: Unit tests for StructuredOutputConverter service.
# ABOUTME: Tests message filtering, conversion success/failure, and error handling.

from unittest.mock import Mock

import pytest
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from dynagent.tools.structured_converter import StructuredOutputConverter


@pytest.fixture
def mock_model():
    """Create a mock ChatGoogleGenerativeAI model."""
    return Mock(spec=ChatGoogleGenerativeAI)


@pytest.fixture
def converter(mock_model):
    """Create a StructuredOutputConverter with mock model."""
    return StructuredOutputConverter(mock_model)


def test_filter_messages_with_handoff(converter):
    """Test message filtering finds handoff and returns messages after it."""
    messages = [
        HumanMessage(content="Start conversation"),
        AIMessage(content="I'll help you"),
        ToolMessage(content="Handoff to preface_agent", tool_call_id="tool_1"),
        HumanMessage(content="What is this about?"),
        AIMessage(content="This document is about..."),
    ]

    filtered = converter._filter_messages_for_agent(messages, "preface_agent")

    # Should get messages after handoff
    assert len(filtered) == 2
    assert filtered[0].content == "What is this about?"
    assert filtered[1].content == "This document is about..."


def test_filter_messages_no_handoff(converter):
    """Test message filtering returns all messages when no handoff found."""
    messages = [
        HumanMessage(content="Start conversation"),
        AIMessage(content="I'll help you"),
        HumanMessage(content="Tell me more"),
    ]

    filtered = converter._filter_messages_for_agent(messages, "coordinator")

    # Should get all messages (coordinator case)
    assert len(filtered) == 3
    assert filtered == messages


def test_filter_messages_multiple_handoffs(converter):
    """Test message filtering uses the last handoff."""
    messages = [
        HumanMessage(content="Start"),
        ToolMessage(content="Handoff to preface_agent", tool_call_id="tool_1"),
        HumanMessage(content="First question"),
        AIMessage(content="First answer"),
        ToolMessage(content="Handoff to preface_agent", tool_call_id="tool_2"),
        HumanMessage(content="Second question"),
        AIMessage(content="Second answer"),
    ]

    filtered = converter._filter_messages_for_agent(messages, "preface_agent")

    # Should get messages after the LAST handoff
    assert len(filtered) == 2
    assert filtered[0].content == "Second question"
    assert filtered[1].content == "Second answer"


def test_create_conversion_prompt(converter):
    """Test conversion prompt generation formats messages correctly."""
    messages = [
        HumanMessage(content="What is this?"),
        AIMessage(content="This is a test"),
    ]

    prompt = converter._create_conversion_prompt(messages)

    assert "Based on the conversation history" in prompt
    assert "HUMAN: What is this?" in prompt
    assert "AI: This is a test" in prompt


def test_convert_missing_required_fields(converter, mock_model):
    """Test conversion handles validation errors for missing fields."""
    # Mock the structured output chain to raise an exception
    mock_structured_llm = Mock()
    error_msg = "Missing required field: audience"
    mock_structured_llm.invoke.side_effect = ValueError(error_msg)
    mock_model.with_structured_output.return_value = mock_structured_llm

    messages = [
        HumanMessage(content="Tell me about this"),
        AIMessage(content="It's a thing"),
    ]

    result, error = converter.convert(
        messages, "vision-agent/01-preface.json", "preface_agent"
    )

    assert result is None
    assert error is not None
    assert "Failed to convert conversation" in error
    assert "Missing required field" in error


def test_convert_invalid_schema(converter):
    """Test conversion handles unknown schema gracefully."""
    messages = [
        HumanMessage(content="Test message"),
        AIMessage(content="Test response"),
    ]

    result, error = converter.convert(
        messages, "vision-agent/99-unknown.json", "unknown_agent"
    )

    assert result is None
    assert error is not None
    assert "Schema file not found" in error


def test_convert_no_messages(converter):
    """Test conversion handles empty message list."""
    messages = []

    result, error = converter.convert(
        messages, "vision-agent/01-preface.json", "preface_agent"
    )

    assert result is None
    assert error is not None
    assert "No conversation history" in error
