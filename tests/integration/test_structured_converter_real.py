# ABOUTME: Integration tests for StructuredConverter with real LLM calls.
# ABOUTME: Validates actual conversation to structured output conversion without mocks.

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from autobots_devtools_shared_lib.dynagent.services.structured_converter import StructuredOutputConverter
from tests.conftest import requires_google_api


@pytest.fixture
def real_converter():
    """Create StructuredConverter with real Gemini model."""
    model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,  # Deterministic for testing
    )
    return StructuredOutputConverter(model)


@requires_google_api
def test_getting_started_conversion_with_collection_data(real_converter):
    """Test converting Collection component conversation to Getting Started schema.

    This is the primary test using real user data about the Collection component.
    Tests that the LLM can extract overview, vision, and success metrics.
    """
    # Create realistic conversation about Collection component
    messages = [
        HumanMessage(content="Tell me about the Collection component"),
        AIMessage(
            content=(
                "The Collection component manages payables and receivables for a "
                "bank, including fees, invoices, refunds, and cashbacks. It solves "
                "the problem of managing partial collections and retries. The "
                "component is accessed via backend APIs."
            )
        ),
        HumanMessage(content="What's the vision for this component?"),
        AIMessage(
            content=(
                "The long-term vision for the Collection component is to be the "
                "sole source of truth for payables and receivables within the "
                "Bank's ecosystem. In the next 1-2 years, it should have the "
                "capability to handle partial collections, dynamic retries, and "
                "split rules. This will enable the business to reduce operational "
                "costs. Key success metrics include increased collection "
                "efficiency, specifically increasing successful collections on "
                "first retry by 10%."
            )
        ),
    ]

    result, error = real_converter.convert(
        messages, "vision-agent/02-getting-started.json", "getting_started_agent"
    )

    # Validate conversion succeeded
    assert error is None, f"Conversion failed: {error}"
    assert result is not None
    assert isinstance(result, dict)

    # Validate required fields exist and meet schema requirements
    assert "overview" in result
    assert isinstance(result["overview"], str)
    assert len(result["overview"]) >= 50, "Overview must be at least 50 characters"

    assert "vision" in result
    assert isinstance(result["vision"], str)
    assert len(result["vision"]) >= 50, "Vision must be at least 50 characters"

    # Validate content quality - key terms should be present
    overview_lower = result["overview"].lower()
    assert any(
        term in overview_lower for term in ["collection", "payable", "receivable"]
    ), "Overview should mention Collection/payables/receivables"

    vision_lower = result["vision"].lower()
    assert any(
        term in vision_lower for term in ["vision", "future", "source of truth"]
    ), "Vision should mention long-term goals"

    # Optional field - if present, validate structure
    if "success_metrics" in result:
        assert isinstance(result["success_metrics"], list)
        if len(result["success_metrics"]) > 0:
            assert all(
                isinstance(metric, str) for metric in result["success_metrics"]
            ), "All success metrics must be strings"


@requires_google_api
def test_preface_conversion_with_payment_gateway(real_converter):
    """Test converting Payment Gateway conversation to Preface schema.

    This is a secondary test using Payment Gateway API example.
    Tests extraction of about_this_guide and audience fields.
    """
    messages = [
        HumanMessage(
            content="I need to create a vision document for our Payment Gateway API"
        ),
        AIMessage(
            content=(
                "Great! Let's start with the preface. This document will serve "
                "as a comprehensive guide to the Payment Gateway API, which "
                "enables merchants to process credit card payments, handle "
                "refunds, and manage transaction data securely. It's designed "
                "for developers integrating payment functionality into their "
                "applications."
            )
        ),
        HumanMessage(content="Who is the audience for this document?"),
        AIMessage(
            content=(
                "The primary audience includes backend developers, integration "
                "engineers, technical architects, and QA engineers. Product "
                "managers may also find the business context sections useful for "
                "understanding capabilities and limitations."
            )
        ),
    ]

    result, error = real_converter.convert(
        messages, "vision-agent/01-preface.json", "preface_agent"
    )

    # Validate conversion succeeded
    assert error is None, f"Conversion failed: {error}"
    assert result is not None
    assert isinstance(result, dict)

    # Validate required fields
    assert "about_this_guide" in result
    assert isinstance(result["about_this_guide"], str)
    assert (
        len(result["about_this_guide"]) >= 20
    ), "about_this_guide must be at least 20 characters"

    assert "audience" in result
    assert isinstance(result["audience"], list)
    assert len(result["audience"]) >= 1, "Must have at least one audience member"
    assert all(
        isinstance(aud, str) for aud in result["audience"]
    ), "All audience items must be strings"

    # Validate content quality
    about_lower = result["about_this_guide"].lower()
    assert any(
        term in about_lower for term in ["guide", "document", "payment", "gateway"]
    ), "about_this_guide should describe the document purpose"

    # Check that audience includes developer-related roles
    audience_lower = [aud.lower() for aud in result["audience"]]
    assert any(
        term in " ".join(audience_lower)
        for term in ["developer", "engineer", "architect"]
    ), "Audience should include technical roles"


@requires_google_api
def test_partial_information_handling(real_converter):
    """Test that converter handles incomplete conversation gracefully.

    Edge case: conversation with minimal information should either:
    1. Infer reasonable values from context
    2. Return an error about missing information

    We don't mandate a specific behavior, but it should not crash.
    """
    messages = [
        HumanMessage(content="We need a vision document"),
        AIMessage(content="I can help you create a vision document."),
    ]

    result, error = real_converter.convert(
        messages, "vision-agent/02-getting-started.json", "getting_started_agent"
    )

    # Should either succeed with inferred values OR fail gracefully with error
    if error is None:
        # If it succeeded, validate basic structure
        assert result is not None
        assert isinstance(result, dict)
        # LLM might have inferred minimal values - just ensure no crash
    else:
        # If it failed, ensure error message is informative
        assert isinstance(error, str)
        assert len(error) > 0
        # Either case is acceptable - we just want graceful handling
