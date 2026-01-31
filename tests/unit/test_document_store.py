# ABOUTME: Unit tests for DocumentStore service.
# ABOUTME: Tests document CRUD, section operations, and dynamic entity management.

import json
from pathlib import Path

import pytest

from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


class TestDocumentStoreCreation:
    """Tests for DocumentStore initialization."""

    def test_creates_base_directory(self, tmp_path: Path) -> None:
        """DocumentStore should create the base directory if it doesn't exist."""
        store_path = tmp_path / "vision-docs"
        store = DocumentStore(base_path=store_path)

        assert store.base_path == store_path
        assert store_path.exists()

    def test_uses_existing_directory(self, tmp_path: Path) -> None:
        """DocumentStore should use an existing directory."""
        store = DocumentStore(base_path=tmp_path)

        assert store.base_path == tmp_path


class TestDocumentCRUD:
    """Tests for document create, read, list, delete operations."""

    def test_create_document(self, temp_store: DocumentStore) -> None:
        """create_document should initialize a new vision document."""
        meta = temp_store.create_document("payment-gateway", "v1")

        assert meta.component == "payment-gateway"
        assert meta.version == "v1"
        assert meta.sections == {}

    def test_create_document_creates_directory(self, temp_store: DocumentStore) -> None:
        """create_document should create the document directory structure."""
        temp_store.create_document("auth-service", "v2")

        doc_dir = temp_store.base_path / "auth-service" / "v2"
        assert doc_dir.exists()
        assert (doc_dir / "_meta.json").exists()

    def test_create_document_writes_meta_json(self, temp_store: DocumentStore) -> None:
        """create_document should write valid _meta.json."""
        temp_store.create_document("gateway", "v1")

        meta_path = temp_store.base_path / "gateway" / "v1" / "_meta.json"
        with open(meta_path) as f:
            data = json.load(f)

        assert data["component"] == "gateway"
        assert data["version"] == "v1"

    def test_get_document_returns_meta(self, temp_store: DocumentStore) -> None:
        """get_document should return the document metadata."""
        temp_store.create_document("test-comp", "v1")

        meta = temp_store.get_document("test-comp", "v1")

        assert meta is not None
        assert meta.component == "test-comp"
        assert meta.version == "v1"

    def test_get_document_returns_none_when_not_found(
        self, temp_store: DocumentStore
    ) -> None:
        """get_document should return None for non-existent documents."""
        meta = temp_store.get_document("nonexistent", "v1")

        assert meta is None

    def test_list_documents_empty(self, temp_store: DocumentStore) -> None:
        """list_documents should return empty list when no documents exist."""
        docs = temp_store.list_documents()

        assert docs == []

    def test_list_documents_returns_all(self, temp_store: DocumentStore) -> None:
        """list_documents should return all document identifiers."""
        temp_store.create_document("comp-a", "v1")
        temp_store.create_document("comp-a", "v2")
        temp_store.create_document("comp-b", "v1")

        docs = temp_store.list_documents()

        assert len(docs) == 3
        assert ("comp-a", "v1") in docs
        assert ("comp-a", "v2") in docs
        assert ("comp-b", "v1") in docs

    def test_delete_document(self, temp_store: DocumentStore) -> None:
        """delete_document should remove the document."""
        temp_store.create_document("to-delete", "v1")

        result = temp_store.delete_document("to-delete", "v1")

        assert result is True
        assert temp_store.get_document("to-delete", "v1") is None

    def test_delete_document_returns_false_when_not_found(
        self, temp_store: DocumentStore
    ) -> None:
        """delete_document should return False for non-existent documents."""
        result = temp_store.delete_document("nonexistent", "v1")

        assert result is False


class TestSectionOperations:
    """Tests for section read, write, and status operations."""

    def test_write_section(self, temp_store: DocumentStore) -> None:
        """write_section should save section content to a file."""
        meta = temp_store.create_document("gateway", "v1")
        content = {"about": "This is the preface", "audience": ["developers"]}

        result = temp_store.write_section(meta, "01-preface", content)

        assert result is True

    def test_write_section_creates_json_file(self, temp_store: DocumentStore) -> None:
        """write_section should create the section JSON file."""
        meta = temp_store.create_document("gateway", "v1")
        content = {"vision": "To be the best"}

        temp_store.write_section(meta, "02-getting-started", content)

        section_path = (
            temp_store.base_path / "gateway" / "v1" / "02-getting-started.json"
        )
        assert section_path.exists()

    def test_read_section(self, temp_store: DocumentStore) -> None:
        """read_section should return section content."""
        meta = temp_store.create_document("gateway", "v1")
        content = {"features": ["auth", "payment"]}
        temp_store.write_section(meta, "03-01-list-of-features", content)

        result = temp_store.read_section(meta, "03-01-list-of-features")

        assert result == content

    def test_read_section_returns_none_when_not_found(
        self, temp_store: DocumentStore
    ) -> None:
        """read_section should return None for non-existent sections."""
        meta = temp_store.create_document("gateway", "v1")

        result = temp_store.read_section(meta, "nonexistent-section")

        assert result is None

    def test_update_section_status(self, temp_store: DocumentStore) -> None:
        """update_section_status should update the status in metadata."""
        meta = temp_store.create_document("gateway", "v1")

        result = temp_store.update_section_status(
            meta, "01-preface", SectionStatus.COMPLETE
        )

        assert result is True

    def test_update_section_status_persists(self, temp_store: DocumentStore) -> None:
        """update_section_status should persist the status change."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.update_section_status(meta, "01-preface", SectionStatus.DRAFT)

        reloaded = temp_store.get_document("gateway", "v1")

        assert reloaded is not None
        assert "01-preface" in reloaded.sections
        assert reloaded.sections["01-preface"].status == SectionStatus.DRAFT


class TestDynamicEntities:
    """Tests for dynamic entity operations."""

    def test_create_entity(self, temp_store: DocumentStore) -> None:
        """create_entity should add an entity to the document."""
        meta = temp_store.create_document("gateway", "v1")

        result = temp_store.create_entity(meta, "payment-profile")

        assert result is True

    def test_create_entity_persists_in_meta(self, temp_store: DocumentStore) -> None:
        """create_entity should persist the entity in metadata."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "transaction-record")

        reloaded = temp_store.get_document("gateway", "v1")

        assert reloaded is not None
        assert "transaction-record" in reloaded.dynamic_items.entities

    def test_create_entity_creates_section_file(
        self, temp_store: DocumentStore
    ) -> None:
        """create_entity should create the entity section file."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "user-account")

        entity_path = (
            temp_store.base_path / "gateway" / "v1" / "05-entity-user-account.json"
        )
        assert entity_path.exists()

    def test_list_entities_empty(self, temp_store: DocumentStore) -> None:
        """list_entities should return empty list when no entities exist."""
        meta = temp_store.create_document("gateway", "v1")

        entities = temp_store.list_entities(meta)

        assert entities == []

    def test_list_entities_returns_all(self, temp_store: DocumentStore) -> None:
        """list_entities should return all entity names."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "entity-a")
        temp_store.create_entity(meta, "entity-b")

        entities = temp_store.list_entities(meta)

        assert len(entities) == 2
        assert "entity-a" in entities
        assert "entity-b" in entities

    def test_delete_entity(self, temp_store: DocumentStore) -> None:
        """delete_entity should remove the entity."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "to-delete")

        result = temp_store.delete_entity(meta, "to-delete")

        assert result is True

    def test_delete_entity_removes_from_meta(self, temp_store: DocumentStore) -> None:
        """delete_entity should remove the entity from metadata."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "to-delete")
        temp_store.delete_entity(meta, "to-delete")

        reloaded = temp_store.get_document("gateway", "v1")

        assert reloaded is not None
        assert "to-delete" not in reloaded.dynamic_items.entities

    def test_delete_entity_removes_file(self, temp_store: DocumentStore) -> None:
        """delete_entity should remove the entity section file."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.create_entity(meta, "to-delete")
        entity_path = (
            temp_store.base_path / "gateway" / "v1" / "05-entity-to-delete.json"
        )
        assert entity_path.exists()

        temp_store.delete_entity(meta, "to-delete")

        assert not entity_path.exists()

    def test_delete_entity_returns_false_when_not_found(
        self, temp_store: DocumentStore
    ) -> None:
        """delete_entity should return False for non-existent entities."""
        meta = temp_store.create_document("gateway", "v1")

        result = temp_store.delete_entity(meta, "nonexistent")

        assert result is False


class TestLastSection:
    """Tests for last_section tracking."""

    def test_write_section_updates_last_section(
        self, temp_store: DocumentStore
    ) -> None:
        """write_section should update last_section in metadata."""
        meta = temp_store.create_document("gateway", "v1")
        temp_store.write_section(meta, "02-getting-started", {"vision": "test"})

        reloaded = temp_store.get_document("gateway", "v1")

        assert reloaded is not None
        assert reloaded.last_section == "02-getting-started"
