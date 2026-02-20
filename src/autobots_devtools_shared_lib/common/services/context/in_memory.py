from collections.abc import Mapping
from typing import Any


class InMemoryContextStore:
    """In-memory implementation of ContextStore.

    Suitable for development, testing, and ephemeral single-process runs.
    Not safe for multi-process deployments.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, context_key: str) -> dict[str, Any] | None:
        return self._store.get(context_key)

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        self._store[context_key] = dict(data)

    def update(self, context_key: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self._store.get(context_key, {})
        # Create a shallow copy to avoid mutating the original dict outside this store
        updated = {**current, **dict(patch)}
        self._store[context_key] = updated
        return updated

    def delete(self, context_key: str) -> None:
        self._store.pop(context_key, None)
