# ABOUTME: Document metadata models for vision documents.
# ABOUTME: Defines SectionMeta, DynamicItems, DocumentMeta with serialization.

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bro_chat.models.status import SectionStatus


def _now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


@dataclass
class SectionMeta:
    """Metadata for a single section in a vision document."""

    status: SectionStatus = SectionStatus.NOT_STARTED
    updated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON storage."""
        return {
            "status": self.status.value,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionMeta":
        """Deserialize from a dictionary."""
        return cls(
            status=SectionStatus(data["status"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class DynamicItems:
    """Tracks dynamic section items (entities and value iterations)."""

    entities: list[str] = field(default_factory=list)
    value_iterations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON storage."""
        return {
            "entities": self.entities.copy(),
            "value_iterations": self.value_iterations.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DynamicItems":
        """Deserialize from a dictionary."""
        return cls(
            entities=data.get("entities", []).copy(),
            value_iterations=data.get("value_iterations", []).copy(),
        )


@dataclass
class DocumentMeta:
    """Metadata for a complete vision document."""

    component: str
    version: str
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    last_section: str | None = None
    sections: dict[str, SectionMeta] = field(default_factory=dict)
    dynamic_items: DynamicItems = field(default_factory=DynamicItems)

    @property
    def doc_path(self) -> str:
        """Return the relative path to this document's directory."""
        return f"{self.component}/{self.version}"

    @property
    def doc_id(self) -> str:
        """Return a unique identifier for this document."""
        return f"{self.component}-{self.version}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON storage."""
        return {
            "component": self.component,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_section": self.last_section,
            "sections": {
                section_id: meta.to_dict() for section_id, meta in self.sections.items()
            },
            "dynamic_items": self.dynamic_items.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentMeta":
        """Deserialize from a dictionary."""
        sections = {
            section_id: SectionMeta.from_dict(meta_data)
            for section_id, meta_data in data.get("sections", {}).items()
        }
        dynamic_items = DynamicItems.from_dict(data.get("dynamic_items", {}))

        return cls(
            component=data["component"],
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_section=data.get("last_section"),
            sections=sections,
            dynamic_items=dynamic_items,
        )
