# ABOUTME: Unit tests for the dynagent base-agent middleware assembly.
# ABOUTME: Verifies the opt-in copilotkit flag is additive and default-safe.

from unittest.mock import MagicMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.agents.middleware import (
    inject_agent_async,
    inject_agent_sync,
)


def test_build_middleware_stack_default_has_no_copilotkit():
    """Default stack is inject_async + summarization, with no CopilotKit middleware."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    model = MagicMock(name="model")
    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
    ) as mock_summarization:
        stack = build_middleware_stack(model)

    assert len(stack) == 2
    assert stack[0] is inject_agent_async
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)
    # Backward-compat: summarization must keep the historical trigger/keep values.
    mock_summarization.assert_called_once_with(
        model=model,
        trigger=("fraction", 0.6),
        keep=("messages", 20),
    )


def test_build_middleware_stack_sync_mode_default_unchanged():
    """sync_mode swaps in inject_agent_sync but stays copilotkit-free by default."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
    ):
        stack = build_middleware_stack(MagicMock(name="model"), sync_mode=True)

    assert len(stack) == 2
    assert stack[0] is inject_agent_sync
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)


def test_build_middleware_stack_copilotkit_appends_middleware():
    """copilotkit=True appends exactly one trailing CopilotKitMiddleware."""
    pytest.importorskip("copilotkit")
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.base_agent.SummarizationMiddleware",
    ):
        stack = build_middleware_stack(MagicMock(name="model"), copilotkit=True)

    assert len(stack) == 3
    assert type(stack[-1]).__name__ == "CopilotKitMiddleware"
