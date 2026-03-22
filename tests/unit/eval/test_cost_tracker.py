# ABOUTME: Tests for the Level 1 cost tracker.
# ABOUTME: Validates Langfuse trace querying and token attribution with mocked client.

from unittest.mock import MagicMock, patch

from autobots_devtools_shared_lib.eval.core.cost_tracker import query_langfuse
from autobots_devtools_shared_lib.eval.models.cost import CostReport


def test_query_returns_none_when_langfuse_unavailable():
    with patch(
        "autobots_devtools_shared_lib.eval.core.cost_tracker.get_langfuse_client",
        return_value=None,
    ):
        result = query_langfuse("session-123")
        assert result is None


def test_query_returns_cost_report_with_mock_trace():
    mock_client = MagicMock()

    # Mock trace fetch
    mock_trace = MagicMock()
    mock_trace.observations = [
        MagicMock(
            type="GENERATION",
            model="gemini-2.0-flash",
            usage=MagicMock(input=3200, output=600, total=3800),
            calculated_total_cost=0.035,
            start_time=MagicMock(timestamp=MagicMock(return_value=1000)),
            end_time=MagicMock(timestamp=MagicMock(return_value=2200)),
        ),
    ]
    mock_client.fetch_trace.return_value = mock_trace

    # Mock session traces lookup
    mock_client.fetch_traces.return_value = MagicMock(data=[MagicMock(id="trace-1")])

    with patch(
        "autobots_devtools_shared_lib.eval.core.cost_tracker.get_langfuse_client",
        return_value=mock_client,
    ):
        result = query_langfuse("session-123")
        assert result is not None
        assert isinstance(result, CostReport)
        assert result.total_input_tokens > 0
