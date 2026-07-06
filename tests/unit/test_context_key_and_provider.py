# ABOUTME: Unit tests for the ambient context_key var and workspace-context provider seam.
# ABOUTME: Distinct from the state-based resolve_context_key / set_context_key_resolver.

import pytest

from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_context_key,
    resolve_workspace_context,
    set_context_key,
    set_workspace_context_provider,
)


@pytest.fixture(autouse=True)
def _reset():
    set_context_key(None)
    set_workspace_context_provider(None)
    yield
    set_context_key(None)
    set_workspace_context_provider(None)


def test_context_key_defaults_to_none():
    assert get_context_key() is None


def test_context_key_round_trips():
    set_context_key("user-7")
    assert get_context_key() == "user-7"
    set_context_key(None)
    assert get_context_key() is None


def test_resolve_workspace_context_passthrough_without_provider():
    ctx = {"user_name": "u", "repo_name": "r"}
    assert resolve_workspace_context(ctx) == ctx


def test_resolve_workspace_context_uses_registered_provider():
    set_workspace_context_provider(lambda ctx: {"workspace_base_path": f"{ctx['user_name']}/x"})
    assert resolve_workspace_context({"user_name": "u"}) == {"workspace_base_path": "u/x"}
