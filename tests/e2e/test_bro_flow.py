# ABOUTME: End-to-end tests for bro agent workflow.
# ABOUTME: Tests complete document creation, section completion, and export flows.

from pathlib import Path

import pytest

from bro_chat.agents.bro import create_bro_agent
from bro_chat.agents.bro_tools import (
    create_bro_document,
    create_bro_entity,
    delete_bro_entity,
    get_bro_document_status,
    list_bro_documents,
    list_bro_entities,
    set_bro_section_status,
    update_bro_section,
)
from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore
from bro_chat.services.markdown_exporter import export_document
from tests.conftest import requires_google_api


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


class TestDocumentCreationFlow:
    """Tests for creating and managing documents."""

    def test_create_new_document(self, temp_store: DocumentStore) -> None:
        """Should create a new vision document."""
        result = create_bro_document(temp_store, "payment-gateway", "v1")

        assert "payment-gateway" in result
        docs = list_bro_documents(temp_store)
        assert "payment-gateway" in docs

    def test_list_multiple_documents(self, temp_store: DocumentStore) -> None:
        """Should list all created documents."""
        create_bro_document(temp_store, "auth-service", "v1")
        create_bro_document(temp_store, "payment-gateway", "v1")
        create_bro_document(temp_store, "payment-gateway", "v2")

        result = list_bro_documents(temp_store)

        assert "auth-service" in result
        assert "payment-gateway" in result


class TestSectionCompletionFlow:
    """Tests for completing document sections."""

    def test_complete_preface_section(self, temp_store: DocumentStore) -> None:
        """Should update and complete the preface section."""
        create_bro_document(temp_store, "test-service", "v1")

        # Write preface content
        content = {
            "about_this_guide": "This document describes the test service.",
            "audience": ["Developers", "Architects"],
            "glossary": [
                {"term": "API", "definition": "Application Programming Interface"}
            ],
        }
        update_result = update_bro_section(
            temp_store, "test-service", "v1", "01-preface", content
        )
        assert "success" in update_result.lower()

        # Set status to complete
        status_result = set_bro_section_status(
            temp_store, "test-service", "v1", "01-preface", "complete"
        )
        assert "success" in status_result.lower()

        # Verify status
        status = get_bro_document_status(temp_store, "test-service", "v1")
        assert "01-preface" in status
        assert "complete" in status.lower()

    def test_complete_multiple_sections(self, temp_store: DocumentStore) -> None:
        """Should complete multiple sections in sequence."""
        create_bro_document(temp_store, "multi-section", "v1")

        # Complete preface
        update_bro_section(
            temp_store,
            "multi-section",
            "v1",
            "01-preface",
            {"about_this_guide": "Test guide", "audience": ["Devs"]},
        )
        set_bro_section_status(
            temp_store, "multi-section", "v1", "01-preface", "complete"
        )

        # Complete getting started
        update_bro_section(
            temp_store,
            "multi-section",
            "v1",
            "02-getting-started",
            {"overview": "Service overview", "vision": "To be the best"},
        )
        set_bro_section_status(
            temp_store, "multi-section", "v1", "02-getting-started", "complete"
        )

        # Verify both sections are complete
        status = get_bro_document_status(temp_store, "multi-section", "v1")
        assert status.count("complete") >= 2


class TestEntityManagementFlow:
    """Tests for managing dynamic entity sections."""

    def test_create_and_list_entities(self, temp_store: DocumentStore) -> None:
        """Should create entities and list them."""
        create_bro_document(temp_store, "entity-test", "v1")

        # Create entities
        create_bro_entity(temp_store, "entity-test", "v1", "user-profile")
        create_bro_entity(temp_store, "entity-test", "v1", "transaction")

        # List entities
        result = list_bro_entities(temp_store, "entity-test", "v1")

        assert "user-profile" in result
        assert "transaction" in result

    def test_delete_entity(self, temp_store: DocumentStore) -> None:
        """Should delete an entity."""
        create_bro_document(temp_store, "delete-test", "v1")
        create_bro_entity(temp_store, "delete-test", "v1", "to-delete")
        create_bro_entity(temp_store, "delete-test", "v1", "to-keep")

        # Delete one entity
        delete_result = delete_bro_entity(temp_store, "delete-test", "v1", "to-delete")
        assert "success" in delete_result.lower() or "deleted" in delete_result.lower()

        # Verify only one remains
        result = list_bro_entities(temp_store, "delete-test", "v1")
        assert "to-delete" not in result
        assert "to-keep" in result


class TestExportFlow:
    """Tests for exporting documents to markdown."""

    def test_export_completed_document(self, temp_store: DocumentStore) -> None:
        """Should export a completed document to markdown."""
        meta = temp_store.create_document("export-test", "v1")

        # Add preface
        temp_store.write_section(
            meta,
            "01-preface",
            {"about_this_guide": "Export test guide", "audience": ["Testers"]},
        )
        temp_store.update_section_status(meta, "01-preface", SectionStatus.COMPLETE)

        # Add getting started
        temp_store.write_section(
            meta,
            "02-getting-started",
            {"overview": "Test overview", "vision": "Test vision"},
        )

        # Export
        markdown = export_document(temp_store, meta)

        assert "# export-test" in markdown
        assert "Export test guide" in markdown
        assert "Test overview" in markdown

    def test_export_with_entities(self, temp_store: DocumentStore) -> None:
        """Should export document including entities."""
        meta = temp_store.create_document("entity-export", "v1")

        # Create entity with content
        temp_store.create_entity(meta, "payment-profile")
        temp_store.write_section(
            meta,
            "05-entity-payment-profile",
            {
                "name": "Payment Profile",
                "description": "Stores payment information",
                "attributes": [
                    {"name": "id", "type": "uuid", "required": True},
                    {"name": "card_number", "type": "string", "required": True},
                ],
            },
        )

        # Export
        markdown = export_document(temp_store, meta)

        assert "Payment Profile" in markdown
        assert "card_number" in markdown


class TestResumeFlow:
    """Tests for resuming in-progress documents."""

    def test_resume_document_shows_status(self, temp_store: DocumentStore) -> None:
        """Should show correct status when resuming."""
        create_bro_document(temp_store, "resume-test", "v1")

        # Complete first section
        update_bro_section(
            temp_store,
            "resume-test",
            "v1",
            "01-preface",
            {"about_this_guide": "Test", "audience": ["Devs"]},
        )
        set_bro_section_status(
            temp_store, "resume-test", "v1", "01-preface", "complete"
        )

        # Start second section
        set_bro_section_status(
            temp_store, "resume-test", "v1", "02-getting-started", "in_progress"
        )

        # Check status shows both sections
        status = get_bro_document_status(temp_store, "resume-test", "v1")

        assert "01-preface" in status
        assert "complete" in status.lower()
        assert "02-getting-started" in status
        assert "in_progress" in status.lower()


@requires_google_api
class TestAgentCreation:
    """Tests that require Google API for agent creation."""

    def test_create_bro_agent(self, temp_store: DocumentStore) -> None:
        """Should create a functional bro agent."""
        agent = create_bro_agent(store=temp_store)

        assert agent is not None
        assert agent.name == "bro-agent"
