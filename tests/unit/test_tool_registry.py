# ABOUTME: Unit tests for the dynagent tool registry.
# ABOUTME: Validates registry returns exactly the expected dynagent-layer tools.

from dynagent.tools.tool_registry import get_tools

EXPECTED_TOOL_NAMES = {
    "handoff",
    "get_agent_list",
    "write_file",
    "read_file",
    "convert_format",
}

BRO_TOOL_NAMES = {
    "update_section",
    "set_section_status",
    "get_document_status",
    "list_documents",
    "create_document",
    "export_markdown",
    "set_document_context",
    "create_entity",
    "list_entities",
    "delete_entity",
}


def test_get_tools_returns_list():
    tools = get_tools()
    assert isinstance(tools, list)


def test_get_tools_count():
    tools = get_tools()
    assert len(tools) == 5


def test_get_tools_has_expected_names():
    tools = get_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOL_NAMES


def test_get_tools_no_bro_specific():
    """Registry must not contain any BRO-layer tools."""
    tools = get_tools()
    names = {t.name for t in tools}
    assert names.isdisjoint(BRO_TOOL_NAMES)


def test_get_tools_all_are_callable():
    """Every tool in the registry must be invocable."""
    tools = get_tools()
    for t in tools:
        assert hasattr(t, "invoke"), f"Tool {t.name} is not invocable"
