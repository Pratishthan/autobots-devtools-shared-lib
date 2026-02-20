from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ContextStore(Protocol):
    """Protocol for session-level context storage.

    Context is modeled as a JSON-serializable mapping of string keys to arbitrary values.
    Implementations are responsible for persistence and retrieval semantics.
    """

    def get(self, context_key: str) -> dict[str, Any] | None:  # pragma: no cover - Protocol
        """Return the context for the given context_key, or None if not found."""

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:  # pragma: no cover - Protocol
        """Replace the context for the given context_key with the provided data."""

    def update(
        self, context_key: str, patch: Mapping[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - Protocol
        """Apply a partial update to the context and return the new value."""
        ...

    def delete(self, context_key: str) -> None:  # pragma: no cover - Protocol
        """Remove any stored context for the given context_key."""
