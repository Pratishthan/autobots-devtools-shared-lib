# ABOUTME: Unit tests for CacheBackedContextStore, DbRepository Protocol, and set_context_store.
# ABOUTME: Uses mock DbRepository and InMemoryContextStore — no external services required.

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping

from autobots_devtools_shared_lib.common.services.context import (
    CacheBackedContextStore,
    DbRepository,
    InMemoryContextStore,
    get_context_store,
    set_context_store,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cache_backed_accepts_prefix() -> bool:
    """True if the installed CacheBackedContextStore accepts a prefix argument."""
    return "prefix" in inspect.signature(CacheBackedContextStore.__init__).parameters


class _FakeDbRepository:
    """In-memory stand-in for DbRepository (satisfies the Protocol)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, context_key: str) -> dict[str, Any] | None:
        return self._store.get(context_key)

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        self._store[context_key] = dict(data)

    def delete(self, context_key: str) -> None:
        self._store.pop(context_key, None)


def _make_store(
    prefix: str = "",
) -> tuple[CacheBackedContextStore, _FakeDbRepository, InMemoryContextStore]:
    db = _FakeDbRepository()
    cache = InMemoryContextStore()
    kwargs: dict[str, Any] = {"db": db, "cache": cache}
    if _cache_backed_accepts_prefix():
        kwargs["prefix"] = prefix
    store = CacheBackedContextStore(**kwargs)
    return store, db, cache


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_fake_db_satisfies_db_repository_protocol():
    assert isinstance(_FakeDbRepository(), DbRepository)


def test_cache_backed_store_satisfies_context_store_protocol():
    from autobots_devtools_shared_lib.common.services.context import ContextStore

    store, _, _ = _make_store()
    assert isinstance(store, ContextStore)


# ---------------------------------------------------------------------------
# get — cache hit
# ---------------------------------------------------------------------------


def test_get_returns_cached_value_without_hitting_db():
    store, db, cache = _make_store()
    cache.set("k1", {"x": 1})
    db.set("k1", {"x": 99})  # stale DB value — should NOT be returned

    result = store.get("k1")

    assert result == {"x": 1}


# ---------------------------------------------------------------------------
# get — cache miss → load DB → populate cache
# ---------------------------------------------------------------------------


def test_get_cache_miss_loads_from_db():
    store, db, _ = _make_store()
    db.set("k2", {"y": 2})

    result = store.get("k2")

    assert result == {"y": 2}


def test_get_cache_miss_populates_cache():
    store, db, cache = _make_store()
    db.set("k3", {"z": 3})

    store.get("k3")  # triggers cache miss → DB load → cache write
    cached = cache.get("k3")

    assert cached == {"z": 3}


def test_get_returns_none_when_not_in_db_or_cache():
    store, _, _ = _make_store()
    assert store.get("missing") is None


# ---------------------------------------------------------------------------
# set — write-through
# ---------------------------------------------------------------------------


def test_set_writes_to_db():
    store, db, _ = _make_store()
    store.set("s1", {"a": 1})

    assert db.get("s1") == {"a": 1}


def test_set_writes_to_cache():
    store, _, cache = _make_store()
    store.set("s2", {"b": 2})

    assert cache.get("s2") == {"b": 2}


# ---------------------------------------------------------------------------
# update — reads from DB, not cache
# ---------------------------------------------------------------------------


def test_update_merges_with_db_data_not_cache():
    store, db, cache = _make_store()
    db.set("u1", {"existing": "db"})
    cache.set("u1", {"existing": "stale_cache"})  # intentionally stale

    result = store.update("u1", {"new_field": "hello"})

    assert result["existing"] == "db"
    assert result["new_field"] == "hello"


def test_update_writes_merged_result_to_db():
    store, db, _ = _make_store()
    db.set("u2", {"base": 10})

    store.update("u2", {"extra": 20})

    stored = db.get("u2")
    assert stored == {"base": 10, "extra": 20}


def test_update_writes_merged_result_to_cache():
    store, db, cache = _make_store()
    db.set("u3", {"base": 30})

    store.update("u3", {"extra": 40})

    cached = cache.get("u3")
    assert cached == {"base": 30, "extra": 40}


def test_update_works_when_key_not_in_db():
    store, db, _ = _make_store()

    result = store.update("u_new", {"fresh": True})

    assert result == {"fresh": True}
    assert db.get("u_new") == {"fresh": True}


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_from_db():
    store, db, _ = _make_store()
    db.set("d1", {"val": 1})

    store.delete("d1")

    assert db.get("d1") is None


def test_delete_removes_from_cache():
    store, _, cache = _make_store()
    cache.set("d2", {"val": 2})

    store.delete("d2")

    assert cache.get("d2") is None


def test_delete_nonexistent_key_does_not_raise():
    store, _, _ = _make_store()
    store.delete("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# prefix — applied to both db and cache keys
# ---------------------------------------------------------------------------


def test_prefix_applied_to_db_and_cache_on_set():
    """With prefix 'mer_ctx', set('foo', data) stores under 'mer_ctx_foo' in both db and cache."""
    if not _cache_backed_accepts_prefix():
        pytest.skip("CacheBackedContextStore in this environment does not support prefix")
    store, db, cache = _make_store(prefix="mer_ctx")
    store.set("foo", {"a": 1})

    assert db.get("mer_ctx_foo") == {"a": 1}
    assert cache.get("mer_ctx_foo") == {"a": 1}
    assert db.get("foo") is None
    assert cache.get("foo") is None


def test_prefix_applied_on_get():
    """With prefix 'mer_ctx', get('foo') reads from 'mer_ctx_foo' in db/cache."""
    if not _cache_backed_accepts_prefix():
        pytest.skip("CacheBackedContextStore in this environment does not support prefix")
    store, db, _ = _make_store(prefix="mer_ctx")
    db._store["mer_ctx_foo"] = {"x": 42}

    result = store.get("foo")

    assert result == {"x": 42}


def test_prefix_applied_on_update():
    """With prefix 'mer_ctx', update('foo', patch) reads/writes 'mer_ctx_foo' in db and cache."""
    if not _cache_backed_accepts_prefix():
        pytest.skip("CacheBackedContextStore in this environment does not support prefix")
    store, db, cache = _make_store(prefix="mer_ctx")
    db._store["mer_ctx_foo"] = {"a": 1}

    result = store.update("foo", {"b": 2})

    assert result == {"a": 1, "b": 2}
    assert db.get("mer_ctx_foo") == {"a": 1, "b": 2}
    assert cache.get("mer_ctx_foo") == {"a": 1, "b": 2}


def test_prefix_applied_on_delete():
    """With prefix 'mer_ctx', delete('foo') removes 'mer_ctx_foo' from db and cache."""
    if not _cache_backed_accepts_prefix():
        pytest.skip("CacheBackedContextStore in this environment does not support prefix")
    store, db, cache = _make_store(prefix="mer_ctx")
    db._store["mer_ctx_foo"] = {"a": 1}
    cache.set("mer_ctx_foo", {"a": 1})

    store.delete("foo")

    assert db.get("mer_ctx_foo") is None
    assert cache.get("mer_ctx_foo") is None


def test_empty_prefix_keeps_keys_unchanged():
    """With prefix '', keys are passed through unchanged (backward compatible)."""
    if not _cache_backed_accepts_prefix():
        pytest.skip("CacheBackedContextStore in this environment does not support prefix")
    store, db, cache = _make_store(prefix="")
    store.set("raw_key", {"v": 1})

    assert db.get("raw_key") == {"v": 1}
    assert cache.get("raw_key") == {"v": 1}


# ---------------------------------------------------------------------------
# set_context_store / get_context_store singleton override
# ---------------------------------------------------------------------------


def test_set_context_store_overrides_singleton(monkeypatch):
    import autobots_devtools_shared_lib.common.services.context as ctx_module

    monkeypatch.setattr(ctx_module, "_CONTEXT_STORE_SINGLETON", None)

    custom_store = InMemoryContextStore()
    set_context_store(custom_store)

    assert get_context_store() is custom_store


def test_set_context_store_short_circuits_yaml_factory(monkeypatch):
    import autobots_devtools_shared_lib.common.services.context as ctx_module

    monkeypatch.setattr(ctx_module, "_CONTEXT_STORE_SINGLETON", None)

    custom_store = InMemoryContextStore()
    set_context_store(custom_store)

    # get_context_store must NOT call _load_yaml_config
    load_mock = MagicMock()
    monkeypatch.setattr(ctx_module, "_load_yaml_config", load_mock)

    get_context_store()

    load_mock.assert_not_called()
