# ABOUTME: Unit tests for the deep-engine backend registry.
# ABOUTME: Covers state/filesystem resolution, override precedence, and unknown-type failure.

import pytest
from deepagents.backends import FilesystemBackend

from autobots_devtools_shared_lib.dynagent.agents.deep_backend import resolve_backend


def test_no_config_returns_none():
    assert resolve_backend(None) is None
    assert resolve_backend({}) is None


def test_state_type_returns_none():
    assert resolve_backend({"type": "state"}) is None


def test_filesystem_type_builds_backend_and_creates_root(tmp_path):
    root = tmp_path / "ws" / "nested"
    backend = resolve_backend({"type": "filesystem", "root_dir": str(root)})
    assert isinstance(backend, FilesystemBackend)
    assert root.is_dir()


def test_override_instance_wins(tmp_path):
    sentinel = FilesystemBackend(root_dir=str(tmp_path))
    resolved = resolve_backend({"type": "state"}, override=sentinel)
    assert resolved is sentinel


def test_unknown_type_fails_fast_listing_choices():
    with pytest.raises(ValueError, match="filesystem"):
        resolve_backend({"type": "s3"})
