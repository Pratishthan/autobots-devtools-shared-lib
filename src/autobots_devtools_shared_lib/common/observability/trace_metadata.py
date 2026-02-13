# ABOUTME: Metadata dataclass for tracing and observability correlation.
# ABOUTME: Encapsulates session IDs, user IDs, app names, and tags for Langfuse.

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraceMetadata:
    """Metadata for tracing and observability correlation.

    Encapsulates all metadata needed for Langfuse tracing, including
    session correlation, user identification, and application context.
    """

    session_id: str
    app_name: str = "default"
    user_id: str = "default"
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        session_id: str | None = None,
        app_name: str = "default",
        user_id: str = "default",
        tags: list[str] | None = None,
    ) -> "TraceMetadata":
        """Create TraceMetadata with auto-generated session_id if needed."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        return cls(
            session_id=session_id[:200],  # Langfuse 200-char limit
            app_name=app_name,
            user_id=user_id,
            tags=tags or [],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TraceMetadata":
        """Create from legacy trace_metadata dict for backward compatibility."""
        if data is None:
            return cls.create()
        return cls.create(
            session_id=data.get("session_id"),
            app_name=data.get("app_name", "default"),
            user_id=data.get("user_id", "default"),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for metadata merging."""
        return asdict(self)
