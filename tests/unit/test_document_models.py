# ABOUTME: Unit tests for document models (SectionStatus, SectionMeta, DocumentMeta).
# ABOUTME: Tests enum values, dataclass creation, and serialization methods.

from datetime import UTC, datetime

from bro_chat.models.document import DocumentMeta, DynamicItems, SectionMeta
from bro_chat.models.status import SectionStatus


class TestSectionStatus:
    """Tests for the SectionStatus enum."""

    def test_has_not_started_value(self) -> None:
        """SectionStatus should have NOT_STARTED value."""
        assert SectionStatus.NOT_STARTED.value == "not_started"

    def test_has_in_progress_value(self) -> None:
        """SectionStatus should have IN_PROGRESS value."""
        assert SectionStatus.IN_PROGRESS.value == "in_progress"

    def test_has_needs_detail_value(self) -> None:
        """SectionStatus should have NEEDS_DETAIL value."""
        assert SectionStatus.NEEDS_DETAIL.value == "needs_detail"

    def test_has_draft_value(self) -> None:
        """SectionStatus should have DRAFT value."""
        assert SectionStatus.DRAFT.value == "draft"

    def test_has_complete_value(self) -> None:
        """SectionStatus should have COMPLETE value."""
        assert SectionStatus.COMPLETE.value == "complete"

    def test_from_string(self) -> None:
        """SectionStatus should be creatable from string value."""
        assert SectionStatus("not_started") == SectionStatus.NOT_STARTED
        assert SectionStatus("in_progress") == SectionStatus.IN_PROGRESS
        assert SectionStatus("complete") == SectionStatus.COMPLETE


class TestSectionMeta:
    """Tests for the SectionMeta dataclass."""

    def test_create_with_defaults(self) -> None:
        """SectionMeta should be creatable with default status."""
        meta = SectionMeta()
        assert meta.status == SectionStatus.NOT_STARTED
        assert meta.updated_at is not None

    def test_create_with_status(self) -> None:
        """SectionMeta should accept a status parameter."""
        meta = SectionMeta(status=SectionStatus.COMPLETE)
        assert meta.status == SectionStatus.COMPLETE

    def test_to_dict(self) -> None:
        """SectionMeta should serialize to a dictionary."""
        now = datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)
        meta = SectionMeta(status=SectionStatus.DRAFT, updated_at=now)

        result = meta.to_dict()

        assert result["status"] == "draft"
        assert result["updated_at"] == "2026-01-31T10:00:00+00:00"

    def test_from_dict(self) -> None:
        """SectionMeta should deserialize from a dictionary."""
        data = {"status": "complete", "updated_at": "2026-01-31T10:00:00+00:00"}

        meta = SectionMeta.from_dict(data)

        assert meta.status == SectionStatus.COMPLETE
        assert meta.updated_at == datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)


class TestDynamicItems:
    """Tests for the DynamicItems dataclass."""

    def test_create_with_defaults(self) -> None:
        """DynamicItems should have empty lists by default."""
        items = DynamicItems()
        assert items.entities == []
        assert items.value_iterations == []

    def test_create_with_items(self) -> None:
        """DynamicItems should accept entity and iteration lists."""
        items = DynamicItems(
            entities=["payment-profile", "transaction"],
            value_iterations=["mvp", "phase-2"],
        )
        assert items.entities == ["payment-profile", "transaction"]
        assert items.value_iterations == ["mvp", "phase-2"]

    def test_to_dict(self) -> None:
        """DynamicItems should serialize to a dictionary."""
        items = DynamicItems(entities=["entity1"], value_iterations=["iter1"])

        result = items.to_dict()

        assert result == {"entities": ["entity1"], "value_iterations": ["iter1"]}

    def test_from_dict(self) -> None:
        """DynamicItems should deserialize from a dictionary."""
        data = {"entities": ["entity1", "entity2"], "value_iterations": ["mvp"]}

        items = DynamicItems.from_dict(data)

        assert items.entities == ["entity1", "entity2"]
        assert items.value_iterations == ["mvp"]


class TestDocumentMeta:
    """Tests for the DocumentMeta dataclass."""

    def test_create_minimal(self) -> None:
        """DocumentMeta should be creatable with just component and version."""
        meta = DocumentMeta(component="payment-gateway", version="v1")

        assert meta.component == "payment-gateway"
        assert meta.version == "v1"
        assert meta.created_at is not None
        assert meta.updated_at is not None
        assert meta.last_section is None
        assert meta.sections == {}
        assert isinstance(meta.dynamic_items, DynamicItems)

    def test_create_full(self) -> None:
        """DocumentMeta should accept all parameters."""
        now = datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)
        section_meta = SectionMeta(status=SectionStatus.COMPLETE, updated_at=now)
        dynamic = DynamicItems(entities=["entity1"])

        meta = DocumentMeta(
            component="auth-service",
            version="v2",
            created_at=now,
            updated_at=now,
            last_section="01-preface",
            sections={"01-preface": section_meta},
            dynamic_items=dynamic,
        )

        assert meta.component == "auth-service"
        assert meta.version == "v2"
        assert meta.last_section == "01-preface"
        assert meta.sections["01-preface"].status == SectionStatus.COMPLETE
        assert meta.dynamic_items.entities == ["entity1"]

    def test_to_dict(self) -> None:
        """DocumentMeta should serialize to a dictionary."""
        now = datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)
        section_meta = SectionMeta(status=SectionStatus.COMPLETE, updated_at=now)

        meta = DocumentMeta(
            component="gateway",
            version="v1",
            created_at=now,
            updated_at=now,
            last_section="01-preface",
            sections={"01-preface": section_meta},
            dynamic_items=DynamicItems(entities=["user"]),
        )

        result = meta.to_dict()

        assert result["component"] == "gateway"
        assert result["version"] == "v1"
        assert result["created_at"] == "2026-01-31T10:00:00+00:00"
        assert result["last_section"] == "01-preface"
        assert result["sections"]["01-preface"]["status"] == "complete"
        assert result["dynamic_items"]["entities"] == ["user"]

    def test_from_dict(self) -> None:
        """DocumentMeta should deserialize from a dictionary."""
        data = {
            "component": "auth",
            "version": "v1",
            "created_at": "2026-01-31T10:00:00+00:00",
            "updated_at": "2026-01-31T14:30:00+00:00",
            "last_section": "03-02",
            "sections": {
                "01-preface": {
                    "status": "complete",
                    "updated_at": "2026-01-31T10:15:00+00:00",
                }
            },
            "dynamic_items": {"entities": ["profile"], "value_iterations": ["mvp"]},
        }

        meta = DocumentMeta.from_dict(data)

        assert meta.component == "auth"
        assert meta.version == "v1"
        assert meta.last_section == "03-02"
        assert meta.sections["01-preface"].status == SectionStatus.COMPLETE
        assert meta.dynamic_items.entities == ["profile"]
        assert meta.dynamic_items.value_iterations == ["mvp"]

    def test_roundtrip_serialization(self) -> None:
        """DocumentMeta should survive a to_dict/from_dict roundtrip."""
        now = datetime(2026, 1, 31, 10, 0, 0, tzinfo=UTC)
        section_meta = SectionMeta(status=SectionStatus.IN_PROGRESS, updated_at=now)

        original = DocumentMeta(
            component="test-comp",
            version="v3",
            created_at=now,
            updated_at=now,
            last_section="02-getting-started",
            sections={"01-preface": section_meta},
            dynamic_items=DynamicItems(entities=["a", "b"], value_iterations=["iter1"]),
        )

        data = original.to_dict()
        restored = DocumentMeta.from_dict(data)

        assert restored.component == original.component
        assert restored.version == original.version
        assert restored.created_at == original.created_at
        assert restored.last_section == original.last_section
        assert restored.sections["01-preface"].status == SectionStatus.IN_PROGRESS
        assert restored.dynamic_items.entities == ["a", "b"]

    def test_doc_path_property(self) -> None:
        """DocumentMeta should provide a path to the document directory."""
        meta = DocumentMeta(component="payment-gateway", version="v1")

        assert meta.doc_path == "payment-gateway/v1"

    def test_doc_id_property(self) -> None:
        """DocumentMeta should provide a document identifier."""
        meta = DocumentMeta(component="payment-gateway", version="v2")

        assert meta.doc_id == "payment-gateway-v2"
