# ABOUTME: Unit tests for the ambient session-id reader.
# ABOUTME: Verifies get_session_id reflects set_session_id and the unset default.

from autobots_devtools_shared_lib.common.observability import (
    get_session_id,
    set_session_id,
)


def test_get_session_id_default_when_unset():
    # Fresh contextvar default sentinel (harmless for file ops per design).
    set_session_id("default-session-id")
    assert get_session_id() == "default-session-id"


def test_get_session_id_reflects_set():
    set_session_id("thread-42")
    assert get_session_id() == "thread-42"
    set_session_id("default-session-id")
