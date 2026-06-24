# ABOUTME: Unit tests for the dynagent base-agent middleware assembly.
# ABOUTME: Verifies the opt-in copilotkit flag is additive and default-safe.

from unittest.mock import MagicMock, patch

import pytest


def test_build_middleware_stack_default_has_no_copilotkit():
    """Default stack is inject + summarization, with no CopilotKit middleware."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    mock_summarization = MagicMock()
    mock_summarization.__class__.__name__ = "SummarizationMiddleware"
    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
        return_value=mock_summarization,
    ):
        stack = build_middleware_stack(MagicMock(name="model"))

    assert len(stack) == 2
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)


def test_build_middleware_stack_sync_mode_default_unchanged():
    """sync_mode swaps the inject middleware but stays copilotkit-free by default."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    mock_summarization = MagicMock()
    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
        return_value=mock_summarization,
    ):
        stack = build_middleware_stack(MagicMock(name="model"), sync_mode=True)

    assert len(stack) == 2
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)


def test_build_middleware_stack_copilotkit_appends_middleware():
    """copilotkit=True appends exactly one trailing CopilotKitMiddleware."""
    pytest.importorskip("copilotkit")
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    mock_summarization = MagicMock()
    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
        return_value=mock_summarization,
    ):
        stack = build_middleware_stack(MagicMock(name="model"), copilotkit=True)

    assert len(stack) == 3
    assert type(stack[-1]).__name__ == "CopilotKitMiddleware"
