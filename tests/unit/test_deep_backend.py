# ABOUTME: Unit tests for the deep-engine backend registry.
# ABOUTME: Covers state/filesystem resolution, override precedence, and unknown-type failure.

from types import SimpleNamespace

import pytest
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

from autobots_devtools_shared_lib.dynagent.agents.deep_backend import resolve_backend
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import FileServerBackend


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
    sentinel = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
    resolved = resolve_backend({"type": "state"}, override=sentinel)
    assert resolved is sentinel


def test_unknown_type_fails_fast_listing_choices():
    with pytest.raises(ValueError, match="filesystem"):
        resolve_backend({"type": "s3"})


def _runtime(state=None):
    return SimpleNamespace(state=state or {})


def test_fserver_type_returns_runtime_factory():
    factory = resolve_backend({"type": "fserver"})
    assert callable(factory)
    # session_id/context_key are resolved lazily from ambient ContextVars now
    # (see FileServerBackend._resolve), not snapshotted from runtime.state.
    backend = factory(_runtime({"session_id": "s1", "jira_number": "J-1", "other": "x"}))
    assert isinstance(backend, FileServerBackend)


def test_store_type_without_store_kwarg_fails_fast():
    with pytest.raises(ValueError, match="store="):
        resolve_backend({"type": "store"})


def test_store_type_with_store_kwarg(monkeypatch):
    sentinel_store = object()
    built = {}

    def fake_store_backend(*, store):
        built["store"] = store
        return StateBackend()  # any BackendProtocol instance

    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.deep_backend.StoreBackend",
        fake_store_backend,
    )
    resolve_backend({"type": "store"}, store=sentinel_store)
    assert built["store"] is sentinel_store


def test_composite_builds_routed_backend():
    factory = resolve_backend(
        {
            "type": "composite",
            "routes": {
                "/workspace/": {"type": "fserver"},
                "/scratch/": {"type": "state"},
            },
        }
    )
    assert callable(factory)
    composite = factory(_runtime({"session_id": "s1"}))
    assert isinstance(composite, CompositeBackend)
    assert isinstance(composite.default, StateBackend)
    assert isinstance(composite.routes["/workspace/"], FileServerBackend)
    assert isinstance(composite.routes["/scratch/"], StateBackend)


def test_composite_store_route_without_store_kwarg_fails_fast():
    config = {"type": "composite", "routes": {"/memories/": {"type": "store"}}}
    with pytest.raises(ValueError, match="store="):
        resolve_backend(config)


def test_unknown_type_error_lists_all_types():
    with pytest.raises(ValueError) as excinfo:
        resolve_backend({"type": "bogus"})
    for name in ("state", "filesystem", "fserver", "store", "composite"):
        assert name in str(excinfo.value)
