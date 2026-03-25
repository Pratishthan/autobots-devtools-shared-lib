"""Unit tests for progress_middleware callback registry."""

from unittest.mock import MagicMock

from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import (
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
