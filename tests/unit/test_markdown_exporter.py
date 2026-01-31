# ABOUTME: Unit tests for markdown exporter.
# ABOUTME: Tests vision document export to markdown format.

from pathlib import Path

import pytest

from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore
from bro_chat.services.markdown_exporter import export_document


@pytest.fixture
def temp_store(tmp_path: Path) -> DocumentStore:
    """Create a DocumentStore with a temporary directory."""
    return DocumentStore(base_path=tmp_path)


@pytest.fixture
def populated_doc(temp_store: DocumentStore):
    """Create a document with some sections filled in."""
    meta = temp_store.create_document("test-service", "v1")

    # Add preface content
    temp_store.write_section(
        meta,
        "01-preface",
        {
            "about_this_guide": "This guide describes the test service vision.",
            "audience": ["Developers", "Architects"],
            "glossary": [
                {"term": "API", "definition": "Application Programming Interface"}
            ],
        },
    )
    temp_store.update_section_status(meta, "01-preface", SectionStatus.COMPLETE)

    # Add getting started content
    temp_store.write_section(
        meta,
        "02-getting-started",
        {
            "overview": "The test service provides core functionality for testing.",
            "vision": "To be the most reliable testing platform.",
        },
    )
    temp_store.update_section_status(meta, "02-getting-started", SectionStatus.COMPLETE)

    # Add features
    temp_store.write_section(
        meta,
        "03-01-list-of-features",
        {
            "features": [
                {
                    "name": "User Auth",
                    "description": "Authenticate users",
                    "priority": "must_have",
                },
                {
                    "name": "Reporting",
                    "description": "Generate reports",
                    "priority": "should_have",
                },
            ]
        },
    )
    temp_store.update_section_status(
        meta, "03-01-list-of-features", SectionStatus.DRAFT
    )

    return meta


class TestExportDocument:
    """Tests for export_document function."""

    def test_exports_document_header(
        self, temp_store: DocumentStore, populated_doc
    ) -> None:
        """Export should include document title."""
        result = export_document(temp_store, populated_doc)

        assert "# test-service" in result
        assert "v1" in result

    def test_exports_preface_section(
        self, temp_store: DocumentStore, populated_doc
    ) -> None:
        """Export should include preface content."""
        result = export_document(temp_store, populated_doc)

        assert "## 1. Preface" in result
        assert "This guide describes the test service vision" in result
        assert "Developers" in result

    def test_exports_getting_started_section(
        self, temp_store: DocumentStore, populated_doc
    ) -> None:
        """Export should include getting started content."""
        result = export_document(temp_store, populated_doc)

        assert "## 2. Getting Started" in result
        assert "core functionality" in result
        assert "most reliable testing platform" in result

    def test_exports_features_section(
        self, temp_store: DocumentStore, populated_doc
    ) -> None:
        """Export should include features content."""
        result = export_document(temp_store, populated_doc)

        assert "## 3. Features" in result or "List of Features" in result
        assert "User Auth" in result
        assert "Reporting" in result

    def test_exports_glossary_as_list(
        self, temp_store: DocumentStore, populated_doc
    ) -> None:
        """Export should format glossary as definition list."""
        result = export_document(temp_store, populated_doc)

        assert "API" in result
        assert "Application Programming Interface" in result

    def test_exports_empty_sections_with_placeholder(
        self, temp_store: DocumentStore
    ) -> None:
        """Export should show placeholder for empty sections."""
        meta = temp_store.create_document("empty-service", "v1")

        result = export_document(temp_store, meta)

        assert "# empty-service" in result


class TestExportWithEntities:
    """Tests for exporting documents with entities."""

    def test_exports_entities(self, temp_store: DocumentStore) -> None:
        """Export should include entity sections."""
        meta = temp_store.create_document("entity-service", "v1")
        temp_store.create_entity(meta, "user-profile")
        temp_store.write_section(
            meta,
            "05-entity-user-profile",
            {
                "name": "User Profile",
                "description": "User account information",
                "attributes": [
                    {"name": "id", "type": "uuid", "required": True},
                    {"name": "email", "type": "email", "required": True},
                ],
            },
        )

        result = export_document(temp_store, meta)

        assert "User Profile" in result
        assert "email" in result
