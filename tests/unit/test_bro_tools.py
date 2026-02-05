# ABOUTME: Unit tests for all 10 BRO document-management tools.
# ABOUTME: Exercises _do_* helpers directly with real DocumentStore on tmp_path.

import json

import pytest

import bro_chat.agents.bro_tools as bro_tools
from bro_chat.services.document_store import DocumentStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Wire both _make_store and WORKSPACE_BASE to tmp_path-local directories."""
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    store = DocumentStore(docs_root)
    monkeypatch.setattr(bro_tools, "_make_store", lambda: store)
    monkeypatch.setenv("WORKSPACE_BASE", str(workspace_root))
    return store


@pytest.fixture
def seed_doc(tmp_store):
    """Create a document so CRUD ops have something to work with."""
    tmp_store.create_document("payment-gateway", "v1")
    return ("payment-gateway", "v1")


@pytest.fixture
def seed_context(tmp_store, seed_doc):  # noqa: ARG001
    """Write _doc_context.json so context-dependent tools can find the doc."""
    bro_tools._write_context("test-session", seed_doc[0], seed_doc[1])
    return seed_doc


# ---------------------------------------------------------------------------
# create_document
# ---------------------------------------------------------------------------


class TestCreateDocument:
    def test_creates_on_disk(self, tmp_store):
        bro_tools._do_create_document("s1", "comp-a", "v2")
        assert tmp_store.get_document("comp-a", "v2") is not None

    def test_writes_context_file(self, tmp_store):  # noqa: ARG001
        bro_tools._do_create_document("s1", "comp-a", "v2")
        ctx = bro_tools._read_context("s1")
        assert ctx == {"component": "comp-a", "version": "v2"}

    def test_returns_success_string(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_create_document("s1", "comp-a", "v2")
        assert "comp-a/v2" in result
        assert "Created" in result


# ---------------------------------------------------------------------------
# set_document_context
# ---------------------------------------------------------------------------


class TestSetDocumentContext:
    def test_switches_context_for_existing_doc(self, seed_doc, tmp_store):  # noqa: ARG001
        result = bro_tools._do_set_document_context("s2", seed_doc[0], seed_doc[1])
        assert "Switched" in result
        ctx = bro_tools._read_context("s2")
        assert ctx == {"component": seed_doc[0], "version": seed_doc[1]}

    def test_errors_for_missing_doc(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_set_document_context("s2", "nope", "v99")
        assert "Error" in result
        assert "does not exist" in result


# ---------------------------------------------------------------------------
# get_document_status
# ---------------------------------------------------------------------------


class TestGetDocumentStatus:
    def test_returns_status_info(self, seed_context):
        result = bro_tools._do_get_document_status("test-session")
        assert seed_context[0] in result
        assert seed_context[1] in result

    def test_errors_without_context(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_get_document_status("no-context-session")
        assert "Error" in result
        assert "no active document" in result


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_returns_doc_list(self, seed_doc):
        result = bro_tools._do_list_documents()
        assert seed_doc[0] in result
        assert seed_doc[1] in result

    def test_empty_when_no_docs(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_list_documents()
        assert "No documents" in result


# ---------------------------------------------------------------------------
# update_section
# ---------------------------------------------------------------------------


class TestUpdateSection:
    def test_writes_section(self, seed_context, tmp_store):
        content = json.dumps({"about_this_guide": "A guide.", "audience": ["devs"]})
        result = bro_tools._do_update_section("test-session", "01-preface", content)
        assert "Updated" in result
        # Verify on disk
        doc = tmp_store.get_document(*seed_context)
        section = tmp_store.read_section(doc, "01-preface")
        assert section["about_this_guide"] == "A guide."

    def test_errors_on_bad_json(self, seed_context):  # noqa: ARG001
        result = bro_tools._do_update_section("test-session", "01-preface", "not json")
        assert "Error" in result
        assert "invalid JSON" in result

    def test_errors_without_context(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_update_section("no-ctx", "01-preface", "{}")
        assert "Error" in result
        assert "no active document" in result


# ---------------------------------------------------------------------------
# set_section_status
# ---------------------------------------------------------------------------


class TestSetSectionStatus:
    def test_updates_status(self, seed_context, tmp_store):
        result = bro_tools._do_set_section_status(
            "test-session", "01-preface", "in_progress"
        )
        assert "in_progress" in result
        # Verify on disk
        doc = tmp_store.get_document(*seed_context)
        assert doc.sections["01-preface"].status.value == "in_progress"

    def test_errors_on_invalid_status(self, seed_context):  # noqa: ARG001
        result = bro_tools._do_set_section_status(
            "test-session", "01-preface", "bogus_status"
        )
        assert "Error" in result
        assert "invalid status" in result

    def test_errors_without_context(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_set_section_status("no-ctx", "01-preface", "draft")
        assert "Error" in result
        assert "no active document" in result


# ---------------------------------------------------------------------------
# export_markdown
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    def test_returns_non_empty_for_seeded_doc(self, seed_context):  # noqa: ARG001
        result = bro_tools._do_export_markdown("test-session")
        assert len(result) > 0
        assert "payment-gateway" in result

    def test_errors_without_context(self, tmp_store):  # noqa: ARG001
        result = bro_tools._do_export_markdown("no-ctx")
        assert "Error" in result
        assert "no active document" in result


# ---------------------------------------------------------------------------
# create_entity / list_entities / delete_entity — full lifecycle
# ---------------------------------------------------------------------------


class TestEntityLifecycle:
    def test_create_entity(self, seed_context, tmp_store):
        result = bro_tools._do_create_entity("test-session", "user-profile")
        assert "Created" in result
        doc = tmp_store.get_document(*seed_context)
        assert "user-profile" in tmp_store.list_entities(doc)

    def test_list_entities(self, seed_context, tmp_store):
        bro_tools._do_create_entity("test-session", "order")
        result = bro_tools._do_list_entities("test-session")
        assert "order" in result

    def test_delete_entity(self, seed_context, tmp_store):
        bro_tools._do_create_entity("test-session", "to-delete")
        result = bro_tools._do_delete_entity("test-session", "to-delete")
        assert "Deleted" in result
        doc = tmp_store.get_document(*seed_context)
        assert "to-delete" not in tmp_store.list_entities(doc)

    def test_delete_entity_not_found(self, seed_context):  # noqa: ARG001
        result = bro_tools._do_delete_entity("test-session", "ghost")
        assert "Error" in result
        assert "not found" in result

    def test_list_entities_empty(self, seed_context):  # noqa: ARG001
        result = bro_tools._do_list_entities("test-session")
        assert "No entities" in result


# ---------------------------------------------------------------------------
# Context-dependent tools error when _doc_context.json is missing
# ---------------------------------------------------------------------------


class TestNoContextErrors:
    """All context-dependent tools must error gracefully without a context file."""

    SESSION = "orphan-session"

    def test_get_document_status(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_get_document_status(self.SESSION)

    def test_update_section(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_update_section(
            self.SESSION, "01-preface", "{}"
        )

    def test_set_section_status(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_set_section_status(
            self.SESSION, "01-preface", "draft"
        )

    def test_export_markdown(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_export_markdown(self.SESSION)

    def test_create_entity(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_create_entity(self.SESSION, "ent")

    def test_list_entities(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_list_entities(self.SESSION)

    def test_delete_entity(self, tmp_store):  # noqa: ARG001
        assert "no active document" in bro_tools._do_delete_entity(self.SESSION, "ent")
