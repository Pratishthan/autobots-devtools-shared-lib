"""Unit tests for progress_middleware callback registry and ProgressPersistenceMiddleware."""

from unittest.mock import MagicMock, patch

from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import (
    ProgressPersistenceMiddleware,
    get_progress_callback,
    set_progress_callback,
)


class TestSetProgressCallback:
    def test_set_and_get(self):
        cb = MagicMock()
        set_progress_callback(cb)
        assert get_progress_callback() is cb
        # Cleanup
        set_progress_callback(None)

    def test_default_is_none(self):
        set_progress_callback(None)
        assert get_progress_callback() is None

    def test_set_none_clears(self):
        cb = MagicMock()
        set_progress_callback(cb)
        set_progress_callback(None)
        assert get_progress_callback() is None

    def test_callback_is_callable(self):
        cb = MagicMock()
        set_progress_callback(cb)
        got = get_progress_callback()
        assert got is not None
        got(
            user_name="alice",
            repo_name="r",
            jira_number="J-1",
            domain="nurture",
            stage="model",
            item="Party",
            status="pending",
        )
        cb.assert_called_once()
        set_progress_callback(None)


class TestProgressPersistenceMiddleware:
    def test_domain_stored(self):
        mw = ProgressPersistenceMiddleware(domain="designer")
        assert mw.domain == "designer"

    def test_after_model_noop_when_no_todos(self):
        """Should return None when state has no todos."""
        mw = ProgressPersistenceMiddleware(domain="nurture")
        result = mw.after_model({"agent_name": "bg"}, MagicMock())
        assert result is None

    @patch("autobots_devtools_shared_lib.dynagent.agents.progress_middleware._progress_callback")
    @patch("autobots_devtools_shared_lib.dynagent.agents.progress_middleware.get_context")
    @patch("autobots_devtools_shared_lib.dynagent.agents.progress_middleware.resolve_context_key")
    def test_after_model_calls_callback_for_each_todo(self, mock_resolve, mock_get_ctx, mock_cb):
        mock_resolve.return_value = "alice"
        mock_get_ctx.return_value = {
            "user_name": "alice",
            "repo_name": "repo",
            "jira_number": "MER-1",
        }

        mw = ProgressPersistenceMiddleware(domain="designer")
        state = {
            "agent_name": "background",
            "todos": [
                {"content": "Read docs", "status": "completed"},
                {"content": "Draft section", "status": "in_progress"},
            ],
        }
        mw.after_model(state, MagicMock())
        assert mock_cb.call_count == 2
