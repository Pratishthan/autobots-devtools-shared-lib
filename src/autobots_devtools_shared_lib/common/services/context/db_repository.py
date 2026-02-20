from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DbRepository(Protocol):
    """Protocol for a database-backed persistence layer used by CacheBackedContextStore.

    Implementations are domain-specific and live in the consuming agent repo.
    The shared-lib depends only on this interface (dependency inversion).
    """

    def get(self, context_key: str) -> dict[str, Any] | None:  # pragma: no cover - Protocol
        """Return the stored data for context_key, or None if not found."""

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:  # pragma: no cover - Protocol
        """Persist data for context_key (upsert semantics)."""

    def delete(self, context_key: str) -> None:  # pragma: no cover - Protocol
        """Remove the stored data for context_key."""
