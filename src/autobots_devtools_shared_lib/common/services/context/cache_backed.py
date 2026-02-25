from collections.abc import Mapping
from typing import Any

from autobots_devtools_shared_lib.common.services.context.db_repository import DbRepository
from autobots_devtools_shared_lib.common.services.context.store import ContextStore


class CacheBackedContextStore:
    """Write-through cache layer: Postgres (via DbRepository) is source of truth, cache is fast read.

    Write-through strategy:
      set/update: 1. Write DB  2. Write cache
      get:        1. Cache hit → return; 2. Cache miss → load DB → populate cache → return
      delete:     1. Remove DB  2. Remove cache

    When prefix is set, the same prefixed key is used for both DB and cache (e.g. for MER
    with prefix \"mer_ctx\", context_key \"user_123\" is stored as \"mer_ctx_user_123\" in both).
    """

    def __init__(
        self,
        db: DbRepository,
        cache: ContextStore,
        *,
        prefix: str = "",
    ) -> None:
        self._db = db
        self._cache = cache
        self._prefix = prefix

    def _key(self, context_key: str) -> str:
        """Return the key used for DB and cache (with prefix when configured)."""
        if not self._prefix:
            return context_key
        return f"{self._prefix}_{context_key}"

    def get(self, context_key: str) -> dict[str, Any] | None:
        key = self._key(context_key)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        # Cache miss — load from DB and repopulate cache
        data = self._db.get(key)
        if data is not None:
            self._cache.set(key, data)
        return data

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        key = self._key(context_key)
        self._db.set(key, data)
        self._cache.set(key, data)

    def update(self, context_key: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        key = self._key(context_key)
        # Read from DB (not cache) to avoid acting on stale cache data
        current = self._db.get(key) or {}
        updated = {**current, **dict(patch)}
        self._db.set(key, updated)
        self._cache.set(key, updated)
        return updated

    def delete(self, context_key: str) -> None:
        key = self._key(context_key)
        self._db.delete(key)
        self._cache.delete(key)
