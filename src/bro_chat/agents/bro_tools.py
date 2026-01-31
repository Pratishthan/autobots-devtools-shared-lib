# ABOUTME: LangChain tools for vision document operations.
# ABOUTME: Provides create, list, status, update, and entity management functions.

import logging
from typing import Any

from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore

logger = logging.getLogger(__name__)


def create_bro_document(store: DocumentStore, component: str, version: str) -> str:
    """Create a new vision document.

    Args:
        store: Document store instance.
        component: Component name (e.g., "payment-gateway").
        version: Version string (e.g., "v1").

    Returns:
        Success message with document identifier.
    """
    meta = store.create_document(component, version)
    return f"Successfully created document: {meta.doc_id}"


def list_bro_documents(store: DocumentStore) -> str:
    """List all available vision documents.

    Args:
        store: Document store instance.

    Returns:
        Formatted list of documents or empty message.
    """
    docs = store.list_documents()
    if not docs:
        return "No documents found."

    lines = [f"- {comp}-{ver}" for comp, ver in docs]
    return "Available documents:\n" + "\n".join(lines)


def get_bro_document_status(store: DocumentStore, component: str, version: str) -> str:
    """Get the status of all sections in a document.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.

    Returns:
        Formatted status table or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    if not meta.sections:
        return f"Document {meta.doc_id}: No sections have been started."

    lines = [f"Document: {meta.doc_id}"]
    lines.append("-" * 40)

    for section_id, section_meta in sorted(meta.sections.items()):
        status_icon = {
            SectionStatus.NOT_STARTED: "⬜",
            SectionStatus.IN_PROGRESS: "🔄",
            SectionStatus.NEEDS_DETAIL: "🟡",
            SectionStatus.DRAFT: "📝",
            SectionStatus.COMPLETE: "✅",
        }.get(section_meta.status, "❓")
        lines.append(f"{status_icon} {section_id}: {section_meta.status.value}")

    if meta.last_section:
        lines.append(f"\nLast worked on: {meta.last_section}")

    return "\n".join(lines)


def update_bro_section(
    store: DocumentStore,
    component: str,
    version: str,
    section_id: str,
    content: dict[str, Any],
) -> str:
    """Update section content.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.
        section_id: Section identifier.
        content: Section content dictionary.

    Returns:
        Success or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    success = store.write_section(meta, section_id, content)
    if success:
        return f"Successfully updated section: {section_id}"
    return f"Error updating section: {section_id}"


def set_bro_section_status(
    store: DocumentStore,
    component: str,
    version: str,
    section_id: str,
    status: str,
) -> str:
    """Set the status of a section.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.
        section_id: Section identifier.
        status: Status string (not_started, in_progress, needs_detail, draft, complete).

    Returns:
        Success or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    try:
        status_enum = SectionStatus(status)
    except ValueError:
        valid = ", ".join(s.value for s in SectionStatus)
        return f"Error: Invalid status '{status}'. Valid: {valid}"

    success = store.update_section_status(meta, section_id, status_enum)
    if success:
        return f"Successfully updated status of {section_id} to {status}"
    return f"Error updating status of {section_id}"


def create_bro_entity(
    store: DocumentStore, component: str, version: str, entity_name: str
) -> str:
    """Create a new entity in the document.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.
        entity_name: Name of the entity to create.

    Returns:
        Success or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    success = store.create_entity(meta, entity_name)
    if success:
        return f"Successfully created entity: {entity_name}"
    return f"Error creating entity: {entity_name}"


def list_bro_entities(store: DocumentStore, component: str, version: str) -> str:
    """List all entities in a document.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.

    Returns:
        Formatted list of entities or empty message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    entities = store.list_entities(meta)
    if not entities:
        return "No entities defined."

    lines = [f"- {entity}" for entity in entities]
    return "Entities:\n" + "\n".join(lines)


def delete_bro_entity(
    store: DocumentStore, component: str, version: str, entity_name: str
) -> str:
    """Delete an entity from the document.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.
        entity_name: Name of the entity to delete.

    Returns:
        Success or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    success = store.delete_entity(meta, entity_name)
    if success:
        return f"Successfully deleted entity: {entity_name}"
    return f"Error: Entity '{entity_name}' not found."


def export_bro_markdown(store: DocumentStore, component: str, version: str) -> str:
    """Export the document as Markdown.

    Args:
        store: Document store instance.
        component: Component name.
        version: Version string.

    Returns:
        Markdown content or error message.
    """
    meta = store.get_document(component, version)
    if not meta:
        return f"Error: Document {component}/{version} not found."

    # Placeholder - will be implemented in markdown_exporter
    return f"# {component} {version}\n\nExport not yet implemented."
