# ABOUTME: Unit tests for the make_context_tools factory in context_tools.py.
# ABOUTME: Verifies correct tool count, names, schema, and deduplication via get_all_tools().

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from autobots_devtools_shared_lib.common.tools.context_tools import make_context_tools
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import (
    _reset_usecase_tools,
    get_all_tools,
    register_usecase_tools,
)

# ---------------------------------------------------------------------------
# Minimal context model for testing
# ---------------------------------------------------------------------------


class _SimpleContext(BaseModel):
    project: str | None = Field(None, description="Project name")
    owner: str | None = Field(None, description="Owner identifier")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_usecase():
    """Isolate every test from prior usecase registrations."""
    _reset_usecase_tools()
    yield
    _reset_usecase_tools()


# ---------------------------------------------------------------------------
# Basic factory behaviour
# ---------------------------------------------------------------------------


def test_make_context_tools_returns_four_tools():
    tools = make_context_tools(_SimpleContext)
    assert len(tools) == 4


def test_make_context_tools_returns_expected_names():
    tools = make_context_tools(_SimpleContext)
    names = {t.name for t in tools}
    assert names == {
        "get_context_tool",
        "set_context_tool",
        "update_context_tool",
        "clear_context_tool",
    }


def test_make_context_tools_all_invocable():
    tools = make_context_tools(_SimpleContext)
    for t in tools:
        assert hasattr(t, "invoke"), f"Tool {t.name} is not invocable"


# ---------------------------------------------------------------------------
# Schema verification — data/patch fields are typed to context_cls
# ---------------------------------------------------------------------------


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    return None


def test_set_context_tool_data_field_in_model_fields():
    """set_context_tool's args_schema must have 'data' in its model_fields."""
    tools = make_context_tools(_SimpleContext)
    set_tool = _find_tool(tools, "set_context_tool")
    assert set_tool is not None

    fields = set_tool.args_schema.model_fields
    assert "data" in fields, f"'data' not found in model_fields: {list(fields)}"


def test_update_context_tool_patch_field_in_model_fields():
    """update_context_tool's args_schema must have 'patch' in its model_fields."""
    tools = make_context_tools(_SimpleContext)
    update_tool = _find_tool(tools, "update_context_tool")
    assert update_tool is not None

    fields = update_tool.args_schema.model_fields
    assert "patch" in fields, f"'patch' not found in model_fields: {list(fields)}"


def test_set_context_tool_data_annotation_is_context_cls():
    """The 'data' field annotation must be the provided context_cls."""
    tools = make_context_tools(_SimpleContext)
    set_tool = _find_tool(tools, "set_context_tool")

    data_field = set_tool.args_schema.model_fields["data"]  # pyright: ignore[reportOptionalMemberAccess]
    # LangChain stores the annotation in the field's annotation attribute
    assert data_field.annotation is _SimpleContext, (
        f"Expected data annotation to be _SimpleContext, got {data_field.annotation}"
    )


# ---------------------------------------------------------------------------
# Deduplication — usecase typed tool overrides default generic tool
# ---------------------------------------------------------------------------


def test_get_all_tools_usecase_overrides_default_by_name():
    """When a usecase tool shares a name with a default tool, the usecase wins."""
    typed_tools = make_context_tools(_SimpleContext)
    register_usecase_tools(typed_tools)

    all_tools = get_all_tools()
    by_name = {t.name: t for t in all_tools}

    # No duplicates — one entry per name
    assert len(all_tools) == len(by_name), "Duplicate tool names found in get_all_tools()"


def test_get_all_tools_no_duplicate_context_tool_names():
    """Registering typed context tools must not produce duplicates."""
    typed_tools = make_context_tools(_SimpleContext)
    register_usecase_tools(typed_tools)

    names = [t.name for t in get_all_tools()]
    for name in (
        "get_context_tool",
        "set_context_tool",
        "update_context_tool",
        "clear_context_tool",
    ):
        assert names.count(name) == 1, f"Tool '{name}' appears more than once in get_all_tools()"


def test_get_all_tools_usecase_typed_tool_is_the_one_returned():
    """The typed tool from usecase registration must be the one in the final pool."""
    typed_tools = make_context_tools(_SimpleContext)
    register_usecase_tools(typed_tools)

    set_tool_from_usecase = _find_tool(typed_tools, "set_context_tool")
    set_tool_in_all = _find_tool(get_all_tools(), "set_context_tool")

    assert set_tool_in_all is set_tool_from_usecase


# ---------------------------------------------------------------------------
# Default tools unchanged when no usecase registration
# ---------------------------------------------------------------------------


def test_make_context_tools_does_not_pollute_defaults():
    """Calling make_context_tools without registering must not change get_all_tools()."""
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_default_tools

    before = {t.name for t in get_default_tools()}
    make_context_tools(_SimpleContext)  # not registered
    after = {t.name for t in get_default_tools()}

    assert before == after
