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
    """

    def __init__(self, db: DbRepository, cache: ContextStore) -> None:
        self._db = db
        self._cache = cache

    def get(self, context_key: str) -> dict[str, Any] | None:
        cached = self._cache.get(context_key)
        if cached is not None:
            return cached
        # Cache miss — load from DB and repopulate cache
        data = self._db.get(context_key)
        if data is not None:
            self._cache.set(context_key, data)
        return data

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        self._db.set(context_key, data)
        self._cache.set(context_key, data)

    def update(self, context_key: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        # Read from DB (not cache) to avoid acting on stale cache data
        current = self._db.get(context_key) or {}
        updated = {**current, **dict(patch)}
        self._db.set(context_key, updated)
        self._cache.set(context_key, updated)
        return updated

    def delete(self, context_key: str) -> None:
        self._db.delete(context_key)
        self._cache.delete(context_key)
