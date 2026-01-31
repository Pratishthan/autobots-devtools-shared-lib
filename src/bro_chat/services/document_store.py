# ABOUTME: Document store service for vision document file I/O.
# ABOUTME: Handles CRUD operations for documents, sections, and dynamic entities.

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from bro_chat.models.document import DocumentMeta, SectionMeta
from bro_chat.models.status import SectionStatus

logger = logging.getLogger(__name__)


class DocumentStore:
    """File-based storage for vision documents."""

    def __init__(self, base_path: Path | str = "vision-docs"):
        """Initialize the document store.

        Args:
            base_path: Directory path for storing vision documents.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _doc_dir(self, component: str, version: str) -> Path:
        """Return the directory path for a document."""
        return self.base_path / component / version

    def _meta_path(self, component: str, version: str) -> Path:
        """Return the path to the _meta.json file."""
        return self._doc_dir(component, version) / "_meta.json"

    def _save_meta(self, meta: DocumentMeta) -> None:
        """Save document metadata to _meta.json."""
        meta_path = self._meta_path(meta.component, meta.version)
        with open(meta_path, "w") as f:
            json.dump(meta.to_dict(), f, indent=2)

    def create_document(self, component: str, version: str) -> DocumentMeta:
        """Create a new vision document.

        Args:
            component: Component name (e.g., "payment-gateway").
            version: Version string (e.g., "v1").

        Returns:
            The newly created DocumentMeta.
        """
        doc_dir = self._doc_dir(component, version)
        doc_dir.mkdir(parents=True, exist_ok=True)

        meta = DocumentMeta(component=component, version=version)
        self._save_meta(meta)

        logger.info(f"Created document: {component}/{version}")
        return meta

    def get_document(self, component: str, version: str) -> DocumentMeta | None:
        """Retrieve document metadata.

        Args:
            component: Component name.
            version: Version string.

        Returns:
            DocumentMeta if found, None otherwise.
        """
        meta_path = self._meta_path(component, version)
        if not meta_path.exists():
            return None

        with open(meta_path) as f:
            data = json.load(f)

        return DocumentMeta.from_dict(data)

    def list_documents(self) -> list[tuple[str, str]]:
        """List all available documents.

        Returns:
            List of (component, version) tuples.
        """
        documents = []

        if not self.base_path.exists():
            return documents

        for component_dir in self.base_path.iterdir():
            if not component_dir.is_dir():
                continue

            for version_dir in component_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                meta_path = version_dir / "_meta.json"
                if meta_path.exists():
                    documents.append((component_dir.name, version_dir.name))

        return documents

    def delete_document(self, component: str, version: str) -> bool:
        """Delete a vision document.

        Args:
            component: Component name.
            version: Version string.

        Returns:
            True if deleted, False if not found.
        """
        doc_dir = self._doc_dir(component, version)
        if not doc_dir.exists():
            return False

        shutil.rmtree(doc_dir)
        logger.info(f"Deleted document: {component}/{version}")
        return True

    def write_section(
        self, meta: DocumentMeta, section_id: str, content: dict[str, Any]
    ) -> bool:
        """Write section content to a file.

        Args:
            meta: Document metadata.
            section_id: Section identifier (e.g., "01-preface").
            content: Section content dictionary.

        Returns:
            True if successful.
        """
        doc_dir = self._doc_dir(meta.component, meta.version)
        section_path = doc_dir / f"{section_id}.json"

        with open(section_path, "w") as f:
            json.dump(content, f, indent=2)

        # Update last_section in metadata
        current_meta = self.get_document(meta.component, meta.version)
        if current_meta:
            current_meta.last_section = section_id
            self._save_meta(current_meta)

        logger.info(f"Wrote section: {meta.doc_id}/{section_id}")
        return True

    def read_section(
        self, meta: DocumentMeta, section_id: str
    ) -> dict[str, Any] | None:
        """Read section content from a file.

        Args:
            meta: Document metadata.
            section_id: Section identifier.

        Returns:
            Section content dictionary if found, None otherwise.
        """
        doc_dir = self._doc_dir(meta.component, meta.version)
        section_path = doc_dir / f"{section_id}.json"

        if not section_path.exists():
            return None

        with open(section_path) as f:
            return json.load(f)

    def update_section_status(
        self, meta: DocumentMeta, section_id: str, status: SectionStatus
    ) -> bool:
        """Update the status of a section.

        Args:
            meta: Document metadata.
            section_id: Section identifier.
            status: New section status.

        Returns:
            True if successful.
        """
        current_meta = self.get_document(meta.component, meta.version)
        if not current_meta:
            return False

        if section_id not in current_meta.sections:
            current_meta.sections[section_id] = SectionMeta(status=status)
        else:
            current_meta.sections[section_id].status = status

        self._save_meta(current_meta)
        logger.info(f"Updated section status: {meta.doc_id}/{section_id} -> {status}")
        return True

    def create_entity(self, meta: DocumentMeta, entity_name: str) -> bool:
        """Create a new entity in the document.

        Args:
            meta: Document metadata.
            entity_name: Entity name (e.g., "payment-profile").

        Returns:
            True if successful.
        """
        current_meta = self.get_document(meta.component, meta.version)
        if not current_meta:
            return False

        if entity_name not in current_meta.dynamic_items.entities:
            current_meta.dynamic_items.entities.append(entity_name)
            self._save_meta(current_meta)

        # Create entity section file
        section_id = f"05-entity-{entity_name}"
        doc_dir = self._doc_dir(meta.component, meta.version)
        entity_path = doc_dir / f"{section_id}.json"
        if not entity_path.exists():
            with open(entity_path, "w") as f:
                json.dump({"name": entity_name, "attributes": []}, f, indent=2)

        logger.info(f"Created entity: {meta.doc_id}/{entity_name}")
        return True

    def list_entities(self, meta: DocumentMeta) -> list[str]:
        """List all entities in a document.

        Args:
            meta: Document metadata.

        Returns:
            List of entity names.
        """
        current_meta = self.get_document(meta.component, meta.version)
        if not current_meta:
            return []

        return current_meta.dynamic_items.entities.copy()

    def delete_entity(self, meta: DocumentMeta, entity_name: str) -> bool:
        """Delete an entity from the document.

        Args:
            meta: Document metadata.
            entity_name: Entity name to delete.

        Returns:
            True if deleted, False if not found.
        """
        current_meta = self.get_document(meta.component, meta.version)
        if not current_meta:
            return False

        if entity_name not in current_meta.dynamic_items.entities:
            return False

        current_meta.dynamic_items.entities.remove(entity_name)
        self._save_meta(current_meta)

        # Remove entity section file
        section_id = f"05-entity-{entity_name}"
        doc_dir = self._doc_dir(meta.component, meta.version)
        entity_path = doc_dir / f"{section_id}.json"
        if entity_path.exists():
            entity_path.unlink()

        logger.info(f"Deleted entity: {meta.doc_id}/{entity_name}")
        return True
