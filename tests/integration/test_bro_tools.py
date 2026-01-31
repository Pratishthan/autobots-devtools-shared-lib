# ABOUTME: Integration tests for bro agent tools.
# ABOUTME: Tests vision-specific tools with real DocumentStore.

from pathlib import Path

import pytest

from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


@pytest.fixture
def sample_doc(temp_store: DocumentStore):
    """Create a sample document for testing."""
    return temp_store.create_document("test-component", "v1")


class TestCreateDocumentTool:
    """Tests for create_document tool."""

    def test_creates_document(self, temp_store: DocumentStore) -> None:
        """Tool should create a new vision document."""
        from bro_chat.agents.bro_tools import create_bro_document

        result = create_bro_document(temp_store, component="new-service", version="v1")

        assert "new-service" in result
        assert temp_store.get_document("new-service", "v1") is not None


class TestListDocumentsTool:
    """Tests for list_documents tool."""

    def test_returns_empty_when_no_docs(self, temp_store: DocumentStore) -> None:
        """Tool should return empty message when no docs exist."""
        from bro_chat.agents.bro_tools import list_bro_documents

        result = list_bro_documents(temp_store)

        assert "no documents" in result.lower() or result == "[]"

    def test_lists_all_documents(self, temp_store: DocumentStore) -> None:
        """Tool should list all available documents."""
        from bro_chat.agents.bro_tools import list_bro_documents

        temp_store.create_document("comp-a", "v1")
        temp_store.create_document("comp-b", "v2")

        result = list_bro_documents(temp_store)

        assert "comp-a" in result
        assert "comp-b" in result


class TestGetDocumentStatusTool:
    """Tests for get_document_status tool."""

    def test_returns_status_for_document(
        self, temp_store: DocumentStore, sample_doc
    ) -> None:
        """Tool should return section statuses for a document."""
        from bro_chat.agents.bro_tools import get_bro_document_status

        temp_store.update_section_status(
            sample_doc, "01-preface", SectionStatus.COMPLETE
        )

        result = get_bro_document_status(
            temp_store, component="test-component", version="v1"
        )

        assert "01-preface" in result
        assert "complete" in result.lower()

    def test_returns_error_for_missing_doc(self, temp_store: DocumentStore) -> None:
        """Tool should return error for non-existent document."""
        from bro_chat.agents.bro_tools import get_bro_document_status

        result = get_bro_document_status(
            temp_store, component="nonexistent", version="v1"
        )

        assert "not found" in result.lower() or "error" in result.lower()


class TestUpdateSectionTool:
    """Tests for update_section tool."""

    def test_updates_section_content(
        self, temp_store: DocumentStore, sample_doc
    ) -> None:
        """Tool should save section content."""
        from bro_chat.agents.bro_tools import update_bro_section

        result = update_bro_section(
            temp_store,
            component="test-component",
            version="v1",
            section_id="01-preface",
            content={"about": "Test content"},
        )

        assert "success" in result.lower() or "updated" in result.lower()

        content = temp_store.read_section(sample_doc, "01-preface")
        assert content is not None
        assert content["about"] == "Test content"


class TestSetSectionStatusTool:
    """Tests for set_section_status tool."""

    def test_sets_status(self, temp_store: DocumentStore, sample_doc) -> None:
        """Tool should set section status."""
        from bro_chat.agents.bro_tools import set_bro_section_status

        result = set_bro_section_status(
            temp_store,
            component="test-component",
            version="v1",
            section_id="01-preface",
            status="complete",
        )

        assert "success" in result.lower() or "updated" in result.lower()

        doc = temp_store.get_document("test-component", "v1")
        assert doc is not None
        assert doc.sections["01-preface"].status == SectionStatus.COMPLETE


class TestEntityTools:
    """Tests for entity management tools."""

    def test_create_entity(self, temp_store: DocumentStore, sample_doc) -> None:
        """Tool should create a new entity."""
        from bro_chat.agents.bro_tools import create_bro_entity

        result = create_bro_entity(
            temp_store,
            component="test-component",
            version="v1",
            entity_name="payment-profile",
        )

        assert "success" in result.lower() or "created" in result.lower()

        entities = temp_store.list_entities(sample_doc)
        assert "payment-profile" in entities

    def test_list_entities(self, temp_store: DocumentStore, sample_doc) -> None:
        """Tool should list all entities."""
        from bro_chat.agents.bro_tools import list_bro_entities

        temp_store.create_entity(sample_doc, "entity-a")
        temp_store.create_entity(sample_doc, "entity-b")

        result = list_bro_entities(temp_store, component="test-component", version="v1")

        assert "entity-a" in result
        assert "entity-b" in result

    def test_delete_entity(self, temp_store: DocumentStore, sample_doc) -> None:
        """Tool should delete an entity."""
        from bro_chat.agents.bro_tools import delete_bro_entity

        temp_store.create_entity(sample_doc, "to-delete")

        result = delete_bro_entity(
            temp_store,
            component="test-component",
            version="v1",
            entity_name="to-delete",
        )

        assert "success" in result.lower() or "deleted" in result.lower()

        entities = temp_store.list_entities(sample_doc)
        assert "to-delete" not in entities
