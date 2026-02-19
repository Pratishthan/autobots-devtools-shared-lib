# ABOUTME: Unit tests for invocation_utils module.
# ABOUTME: Tests invoke_agent and ainvoke_agent with mocked agent (no real API calls).

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.dynagent.agents.invocation_utils import (
    ainvoke_agent,
    invoke_agent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_agent():
    """Create a mock CompiledStateGraph with invoke/ainvoke methods."""
    agent = MagicMock()
    agent.invoke = Mock(
        return_value={
            "messages": [
                {"role": "user", "content": "test"},
                {"role": "ai", "content": "response"},
            ],
            "structured_response": {"joke": "Why did the chicken cross the road?"},
        }
    )
    agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {"role": "user", "content": "test async"},
                {"role": "ai", "content": "async response"},
            ],
            "structured_response": {"joke": "To get to the other side!"},
        }
    )
    return agent


@pytest.fixture
def mock_create_base_agent(mock_agent):
    """Mock create_base_agent to return a mock agent."""
    with patch("autobots_devtools_shared_lib.dynagent.agents.base_agent.create_base_agent") as mock:
        mock.return_value = mock_agent
        yield mock


@pytest.fixture
def mock_get_agent_list():
    """Mock get_agent_list to return valid agent names."""
    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_agent_list"
    ) as mock:
        mock.return_value = ["coordinator", "joke_agent", "preface_agent"]
        yield mock


@pytest.fixture
def input_state():
    """Create a basic input state."""
    return {"messages": [{"role": "user", "content": "Tell me a joke"}]}


@pytest.fixture
def config():
    """Create a basic RunnableConfig."""
    return {"configurable": {"thread_id": "test-thread-123"}}


# ---------------------------------------------------------------------------
# invoke_agent tests
# ---------------------------------------------------------------------------


class TestInvokeAgent:
    def test_invokes_agent_with_correct_state(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that agent.invoke is called with the correct state."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args
        assert "messages" in call_args[0][0]
        assert call_args[1]["config"] == config

    def test_returns_agent_result(
        self, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that the function returns the agent's result."""
        result = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        assert "messages" in result
        assert "structured_response" in result
        assert result["structured_response"]["joke"] == "Why did the chicken cross the road?"

    def test_adds_session_id_to_input_state(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that session_id is added to input_state if missing."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Check that session_id was added to the state passed to agent
        call_args = mock_agent.invoke.call_args
        state_arg = call_args[0][0]
        assert "session_id" in state_arg
        assert isinstance(state_arg["session_id"], str)

    def test_adds_agent_name_to_input_state(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that agent_name is added to input_state if missing."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Check that agent_name was added to the state passed to agent
        call_args = mock_agent.invoke.call_args
        state_arg = call_args[0][0]
        assert "agent_name" in state_arg
        assert state_arg["agent_name"] == "coordinator"

    def test_preserves_existing_session_id(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, config
    ):
        """Test that existing session_id in input_state is preserved."""
        input_state = {
            "messages": [{"role": "user", "content": "test"}],
            "session_id": "my-custom-session",
        }
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        call_args = mock_agent.invoke.call_args
        state_arg = call_args[0][0]
        assert state_arg["session_id"] == "my-custom-session"

    def test_uses_provided_trace_metadata(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that provided TraceMetadata is used."""
        metadata = TraceMetadata(
            session_id="custom-session",
            app_name="test-app",
            user_id="user-123",
            tags=["test", "unit"],
        )

        _ = invoke_agent(
            "coordinator", input_state, config=config, enable_tracing=False, trace_metadata=metadata
        )

        # Verify session_id from metadata was used
        call_args = mock_agent.invoke.call_args
        state_arg = call_args[0][0]
        assert state_arg["session_id"] == "custom-session"

    def test_raises_error_for_unknown_agent(self, mock_get_agent_list, input_state, config):
        """Test that ValueError is raised for unknown agent."""
        with pytest.raises(ValueError, match="Unknown agent: invalid_agent"):
            _ = invoke_agent("invalid_agent", input_state, config=config, enable_tracing=False)

    def test_creates_agent_with_correct_parameters(
        self, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that create_base_agent is called with correct parameters."""
        _ = invoke_agent("joke_agent", input_state, config=config, enable_tracing=False)

        mock_create_base_agent.assert_called_once()
        call_kwargs = mock_create_base_agent.call_args[1]
        assert call_kwargs["sync_mode"] is True
        assert call_kwargs["initial_agent_name"] == "joke_agent"

    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.get_langfuse_handler")
    def test_adds_langfuse_callback_when_tracing_enabled(
        self,
        mock_get_handler,
        mock_get_agent_list,
        mock_create_base_agent,
        mock_agent,
        input_state,
        config,
    ):
        """Test that Langfuse handler is added to callbacks when tracing is enabled."""
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=True)

        # Check that handler was added to config
        call_args = mock_agent.invoke.call_args
        config_arg = call_args[1]["config"]
        assert "callbacks" in config_arg
        assert mock_handler in config_arg["callbacks"]

    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.get_langfuse_handler")
    def test_preserves_existing_callbacks(
        self,
        mock_get_handler,
        mock_get_agent_list,
        mock_create_base_agent,
        mock_agent,
        input_state,
        config,
    ):
        """Test that existing callbacks are preserved."""
        existing_callback = MagicMock()
        config["callbacks"] = [existing_callback]

        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=True)

        call_args = mock_agent.invoke.call_args
        config_arg = call_args[1]["config"]
        assert existing_callback in config_arg["callbacks"]
        assert mock_handler in config_arg["callbacks"]

    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.flush_tracing")
    def test_flushes_tracing_when_enabled(
        self, mock_flush, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that flush_tracing is called when tracing is enabled."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=True)

        mock_flush.assert_called_once()

    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.flush_tracing")
    def test_does_not_flush_when_tracing_disabled(
        self, mock_flush, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that flush_tracing is not called when tracing is disabled."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        mock_flush.assert_not_called()

    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.logger")
    def test_logs_invocation(
        self, mock_logger, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that invocation is logged."""
        _ = invoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Should log at start and end
        assert mock_logger.info.call_count >= 2


# ---------------------------------------------------------------------------
# ainvoke_agent tests
# ---------------------------------------------------------------------------


class TestAinvokeAgent:
    @pytest.mark.asyncio
    async def test_invokes_agent_async_with_correct_state(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that agent.ainvoke is called with the correct state."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        mock_agent.ainvoke.assert_called_once()
        call_args = mock_agent.ainvoke.call_args
        assert "messages" in call_args[0][0]
        assert call_args[1]["config"] == config

    @pytest.mark.asyncio
    async def test_returns_agent_result_async(
        self, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that the async function returns the agent's result."""
        result = await ainvoke_agent(
            "coordinator", input_state, config=config, enable_tracing=False
        )

        assert "messages" in result
        assert "structured_response" in result
        assert result["structured_response"]["joke"] == "To get to the other side!"

    @pytest.mark.asyncio
    async def test_adds_session_id_to_input_state_async(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that session_id is added to input_state if missing (async)."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Check that session_id was added to the state passed to agent
        call_args = mock_agent.ainvoke.call_args
        state_arg = call_args[0][0]
        assert "session_id" in state_arg
        assert isinstance(state_arg["session_id"], str)

    @pytest.mark.asyncio
    async def test_adds_agent_name_to_input_state_async(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that agent_name is added to input_state if missing (async)."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Check that agent_name was added to the state passed to agent
        call_args = mock_agent.ainvoke.call_args
        state_arg = call_args[0][0]
        assert "agent_name" in state_arg
        assert state_arg["agent_name"] == "coordinator"

    @pytest.mark.asyncio
    async def test_preserves_existing_session_id_async(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, config
    ):
        """Test that existing session_id in input_state is preserved (async)."""
        input_state = {
            "messages": [{"role": "user", "content": "test"}],
            "session_id": "my-custom-session-async",
        }
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        call_args = mock_agent.ainvoke.call_args
        state_arg = call_args[0][0]
        assert state_arg["session_id"] == "my-custom-session-async"

    @pytest.mark.asyncio
    async def test_uses_provided_trace_metadata_async(
        self, mock_get_agent_list, mock_create_base_agent, mock_agent, input_state, config
    ):
        """Test that provided TraceMetadata is used (async)."""
        metadata = TraceMetadata(
            session_id="custom-session-async",
            app_name="test-app",
            user_id="user-456",
            tags=["test", "async"],
        )

        _ = await ainvoke_agent(
            "coordinator", input_state, config=config, enable_tracing=False, trace_metadata=metadata
        )

        # Verify session_id from metadata was used
        call_args = mock_agent.ainvoke.call_args
        state_arg = call_args[0][0]
        assert state_arg["session_id"] == "custom-session-async"

    @pytest.mark.asyncio
    async def test_raises_error_for_unknown_agent_async(
        self, mock_get_agent_list, input_state, config
    ):
        """Test that ValueError is raised for unknown agent (async)."""
        with pytest.raises(ValueError, match="Unknown agent: invalid_agent"):
            _ = await ainvoke_agent(
                "invalid_agent", input_state, config=config, enable_tracing=False
            )

    @pytest.mark.asyncio
    async def test_creates_agent_with_correct_parameters_async(
        self, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that create_base_agent is called with correct parameters (async)."""
        _ = await ainvoke_agent("joke_agent", input_state, config=config, enable_tracing=False)

        mock_create_base_agent.assert_called_once()
        call_kwargs = mock_create_base_agent.call_args[1]
        assert call_kwargs["sync_mode"] is False
        assert call_kwargs["initial_agent_name"] == "joke_agent"

    @pytest.mark.asyncio
    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.get_langfuse_handler")
    async def test_adds_langfuse_callback_when_tracing_enabled_async(
        self,
        mock_get_handler,
        mock_get_agent_list,
        mock_create_base_agent,
        mock_agent,
        input_state,
        config,
    ):
        """Test that Langfuse handler is added to callbacks when tracing is enabled (async)."""
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler

        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=True)

        # Check that handler was added to config
        call_args = mock_agent.ainvoke.call_args
        config_arg = call_args[1]["config"]
        assert "callbacks" in config_arg
        assert mock_handler in config_arg["callbacks"]

    @pytest.mark.asyncio
    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.flush_tracing")
    async def test_flushes_tracing_when_enabled_async(
        self, mock_flush, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that flush_tracing is called when tracing is enabled (async)."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=True)

        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.flush_tracing")
    async def test_does_not_flush_when_tracing_disabled_async(
        self, mock_flush, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that flush_tracing is not called when tracing is disabled (async)."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        mock_flush.assert_not_called()

    @pytest.mark.asyncio
    @patch("autobots_devtools_shared_lib.dynagent.agents.invocation_utils.logger")
    async def test_logs_invocation_async(
        self, mock_logger, mock_get_agent_list, mock_create_base_agent, input_state, config
    ):
        """Test that invocation is logged (async)."""
        _ = await ainvoke_agent("coordinator", input_state, config=config, enable_tracing=False)

        # Should log at start and end
        assert mock_logger.info.call_count >= 2
