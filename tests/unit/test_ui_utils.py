# ABOUTME: Unit tests for the shared dynagent UI utility functions.
# ABOUTME: Covers structured_to_markdown, format_dict_item, and _extract_output_type.


from dynagent.ui.ui_utils import (
    _extract_output_type,
    format_dict_item,
    structured_to_markdown,
)

# --- structured_to_markdown ---


def test_structured_to_markdown_simple():
    """Basic key/value dict converts to Markdown with title and bold keys."""
    data = {"name": "Widget", "price": 9.99}
    result = structured_to_markdown(data, title="Product")

    assert "## Product" in result
    assert "**Name:** Widget" in result
    assert "**Price:** 9.99" in result


def test_structured_to_markdown_with_list():
    """List values render as bullet points under a bold heading."""
    data = {"tags": ["fast", "cheap", "reliable"], "count": 3}
    result = structured_to_markdown(data, title="Tags")

    assert "## Tags" in result
    assert "**Tags:**" in result
    assert "- fast" in result
    assert "- cheap" in result
    assert "- reliable" in result
    assert "**Count:** 3" in result


def test_structured_to_markdown_with_nested_dict():
    """Nested dicts are rendered via format_dict_item as indented key/value pairs."""
    data = {
        "config": {"host": "localhost", "port": 8080},
        "enabled": True,
    }
    result = structured_to_markdown(data, title="Settings")

    assert "## Settings" in result
    assert "**Config:**" in result
    assert "- **Host:** localhost" in result
    assert "- **Port:** 8080" in result
    assert "**Enabled:** True" in result


# --- format_dict_item ---


def test_format_dict_item_flat():
    """Flat dict produces one bullet per key at the given indent level."""
    item = {"alpha": "a", "beta": "b"}
    result = format_dict_item(item, indent=0)

    assert "- **Alpha:** a" in result
    assert "- **Beta:** b" in result


def test_format_dict_item_nested():
    """Nested dict recurses and increases indent."""
    item = {"outer": {"inner_key": "inner_val"}}
    result = format_dict_item(item, indent=0)

    # Outer key present at indent 0
    assert "- **Outer:**" in result
    # Inner key present at indent 1 (2 spaces prefix)
    assert "  - **Inner Key:** inner_val" in result


# --- _extract_output_type ---


def test_extract_output_type_standard():
    """'features_agent' strips '_agent' suffix → 'features'."""
    assert _extract_output_type("features_agent") == "features"


def test_extract_output_type_none():
    """None input returns None."""
    assert _extract_output_type(None) is None


def test_extract_output_type_no_suffix():
    """Step name without '_agent' is returned with underscores stripped."""
    assert _extract_output_type("coordinator") == "coordinator"
