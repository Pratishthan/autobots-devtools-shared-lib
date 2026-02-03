# ABOUTME: Unit tests for Markdown formatting utilities.
# ABOUTME: Validates conversion of structured outputs to readable Markdown.

from bro_chat.utils.formatting import (
    format_dict_item,
    format_entity_output,
    format_features_output,
    format_preface_output,
    format_structured_output,
    structured_to_markdown,
)


def test_simple_structured_to_markdown():
    """Basic dict to markdown conversion."""
    data = {
        "answer": 42.0,
        "explanation": "The answer to life, universe, and everything",
    }
    markdown = structured_to_markdown(data, title="Math Result")

    assert "## Math Result" in markdown
    assert "**Answer:** 42.0" in markdown
    assert "**Explanation:** The answer to life, universe, and everything" in markdown


def test_structured_to_markdown_with_lists():
    """Test markdown conversion with list values."""
    data = {"features": ["Login", "Logout", "Profile"], "count": 3}
    markdown = structured_to_markdown(data, title="Features")

    assert "## Features" in markdown
    assert "**Features:**" in markdown
    assert "- Login" in markdown
    assert "- Logout" in markdown
    assert "- Profile" in markdown
    assert "**Count:** 3" in markdown


def test_structured_to_markdown_with_nested_dicts():
    """Test markdown conversion with nested dict objects."""
    data = {
        "user": {"name": "Alice", "role": "admin"},
        "active": True,
    }
    markdown = structured_to_markdown(data)

    assert "**User:**" in markdown
    assert "- **Name:** Alice" in markdown
    assert "- **Role:** admin" in markdown
    assert "**Active:** True" in markdown


def test_format_dict_item():
    """Test formatting of dictionary items."""
    item = {"name": "Test", "value": 123, "nested": {"key": "value"}}
    result = format_dict_item(item)

    assert "- **Name:** Test" in result
    assert "- **Value:** 123" in result
    assert "- **Nested:**" in result
    assert "- **Key:** value" in result


def test_format_dict_item_with_indent():
    """Test indentation in formatted dict items."""
    item = {"field": "value"}
    result = format_dict_item(item, indent=2)

    assert result.startswith("    - **Field:** value")  # 2 * 2 spaces


def test_format_features_output():
    """Test features list formatting."""
    data = {
        "features": [
            {
                "name": "User Login",
                "description": "Allow users to authenticate",
                "category": "core",
                "priority": "must_have",
            },
            {
                "name": "Password Reset",
                "description": "Reset forgotten passwords via email",
                "category": "security",
                "priority": "should_have",
            },
        ]
    }
    markdown = format_features_output(data)

    assert "## Features List" in markdown
    assert "### 1. User Login" in markdown
    assert "Allow users to authenticate" in markdown
    assert "**Category:** core" in markdown
    assert "**Priority:** must_have" in markdown
    assert "### 2. Password Reset" in markdown
    assert "Reset forgotten passwords via email" in markdown


def test_format_features_output_empty():
    """Test features formatting with empty list."""
    data = {"features": []}
    markdown = format_features_output(data)

    assert "## Features List" in markdown


def test_format_preface_output():
    """Test preface formatting."""
    data = {
        "about_this_guide": "This document describes the payment system",
        "audience": ["Product Managers", "Engineers", "QA Team"],
        "reference_documents": [{"name": "API Spec", "url": "https://example.com/api"}],
        "glossary": [
            {
                "term": "PCI DSS",
                "definition": "Payment Card Industry Data Security Standard",
            }
        ],
    }
    markdown = format_preface_output(data)

    assert "## Preface" in markdown
    assert "This document describes the payment system" in markdown
    assert "- Product Managers" in markdown
    assert "- Engineers" in markdown
    assert "- [API Spec](https://example.com/api)" in markdown
    assert "- **PCI DSS:** Payment Card Industry Data Security Standard" in markdown


def test_format_preface_output_minimal():
    """Test preface with only required fields."""
    data = {
        "about_this_guide": "Simple guide",
        "audience": ["Developers"],
    }
    markdown = format_preface_output(data)

    assert "## Preface" in markdown
    assert "Simple guide" in markdown
    assert "- Developers" in markdown


def test_format_preface_reference_without_url():
    """Test preface reference document without URL."""
    data = {
        "about_this_guide": "Guide",
        "audience": ["Dev"],
        "reference_documents": [{"name": "Internal Doc"}],
    }
    markdown = format_preface_output(data)

    assert "- Internal Doc" in markdown
    assert "[Internal Doc]" not in markdown  # Not a link without URL


def test_format_entity_output():
    """Test entity formatting."""
    data = {
        "name": "Order",
        "description": "Customer order entity",
        "purpose": "Track customer purchases",
        "attributes": [
            {
                "name": "order_id",
                "type": "uuid",
                "required": True,
                "description": "Unique identifier",
            },
            {
                "name": "total",
                "type": "number",
                "required": True,
                "description": "Order total",
                "constraints": {"minimum": 0.0},
            },
        ],
        "relationships": [
            {
                "entity": "Customer",
                "type": "many-to-one",
                "required": True,
                "description": "Order owner",
            }
        ],
        "business_rules": [
            "Total must be positive",
            "Cannot delete after shipping",
        ],
    }
    markdown = format_entity_output(data)

    assert "## Entity: Order" in markdown
    assert "**Description:** Customer order entity" in markdown
    assert "**Purpose:** Track customer purchases" in markdown
    assert "### Attributes" in markdown
    assert "**order_id** - `uuid` (required)" in markdown
    assert "- Unique identifier" in markdown
    assert "**total** - `number` (required)" in markdown
    assert "- Constraints: minimum: 0.0" in markdown
    assert "### Relationships" in markdown
    assert "**Customer** - `many-to-one` (required)" in markdown
    assert "- Order owner" in markdown
    assert "### Business Rules" in markdown
    assert "- Total must be positive" in markdown
    assert "- Cannot delete after shipping" in markdown


def test_format_entity_output_minimal():
    """Test entity with only required fields."""
    data = {
        "name": "User",
        "description": "System user",
        "attributes": [{"name": "id", "type": "uuid"}],
    }
    markdown = format_entity_output(data)

    assert "## Entity: User" in markdown
    assert "**Description:** System user" in markdown
    assert "**id** - `uuid`" in markdown
    assert "### Relationships" not in markdown
    assert "### Business Rules" not in markdown


def test_format_structured_output_with_type():
    """Test that specialized formatters are used when type is specified."""
    data = {
        "features": [
            {
                "name": "Test",
                "description": "Test feature",
                "category": "core",
                "priority": "should_have",
            }
        ]
    }

    markdown = format_structured_output(data, output_type="features")

    # Should use specialized formatter
    assert "## Features List" in markdown
    assert "### 1. Test" in markdown


def test_format_structured_output_generic():
    """Test fallback to generic formatter."""
    data = {"custom_field": "value", "nested": {"key": "nested_value"}}

    markdown = format_structured_output(data)

    # Should use generic formatter
    assert "**Custom Field:** value" in markdown
    assert "**Nested:**" in markdown
    assert "- **Key:** nested_value" in markdown


def test_format_structured_output_preface_type():
    """Test preface-specific formatting."""
    data = {
        "about_this_guide": "Test guide",
        "audience": ["Dev"],
    }

    markdown = format_structured_output(data, output_type="preface")

    assert "## Preface" in markdown
    assert "**About This Guide:**" in markdown


def test_format_structured_output_entity_type():
    """Test entity-specific formatting."""
    data = {
        "name": "Product",
        "description": "Product entity",
        "attributes": [{"name": "sku", "type": "string"}],
    }

    markdown = format_structured_output(data, output_type="entity")

    assert "## Entity: Product" in markdown
    assert "### Attributes" in markdown
