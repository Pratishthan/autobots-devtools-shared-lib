# ABOUTME: Unit tests for the dynagent tool registry.
# ABOUTME: Validates default pool, usecase registration, and combined accessors.

import pytest

from dynagent.tools.tool_registry import (
    _reset_usecase_tools,
    get_all_tools,
    get_default_tools,
    get_usecase_tools,
    register_usecase_tools,
)

EXPECTED_DEFAULT_NAMES = {
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


@pytest.fixture(autouse=True)
def reset_usecase():
    """Isolate every test from prior usecase registrations."""
    _reset_usecase_tools()
    yield
    _reset_usecase_tools()


# --- get_default_tools (was get_tools) ---


def test_get_default_tools_returns_list():
    tools = get_default_tools()
    assert isinstance(tools, list)


def test_get_default_tools_count():
    tools = get_default_tools()
    assert len(tools) == 5


def test_get_default_tools_has_expected_names():
    tools = get_default_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_DEFAULT_NAMES


def test_get_default_tools_no_bro_specific():
    """Default pool must not contain any BRO-layer tools."""
    tools = get_default_tools()
    names = {t.name for t in tools}
    assert names.isdisjoint(BRO_TOOL_NAMES)


def test_get_default_tools_all_are_callable():
    """Every default tool must be invocable."""
    tools = get_default_tools()
    for t in tools:
        assert hasattr(t, "invoke"), f"Tool {t.name} is not invocable"


# --- usecase registration ---


class _FakeTool:
    """Minimal stand-in for a langchain tool object."""

    def __init__(self, name: str):
        self.name = name


def test_register_usecase_tools_adds_to_pool():
    fake = _FakeTool("fake_tool")
    register_usecase_tools([fake])
    assert fake in get_usecase_tools()


def test_get_usecase_tools_returns_copy():
    """Mutating the returned list must not affect the internal pool."""
    fake = _FakeTool("copy_test")
    register_usecase_tools([fake])
    pool = get_usecase_tools()
    pool.clear()
    # Internal pool untouched
    assert fake in get_usecase_tools()


def test_get_all_tools_is_union():
    fake = _FakeTool("union_tool")
    register_usecase_tools([fake])
    all_tools = get_all_tools()
    names = {t.name for t in all_tools}
    assert names == EXPECTED_DEFAULT_NAMES | {"union_tool"}


def test_get_default_tools_stable_after_registration():
    """Registering usecase tools must not pollute the default set."""
    register_usecase_tools([_FakeTool("interloper")])
    names = {t.name for t in get_default_tools()}
    assert names == EXPECTED_DEFAULT_NAMES
