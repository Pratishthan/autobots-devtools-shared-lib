# ABOUTME: Markdown exporter for vision documents.
# ABOUTME: Converts JSON sections to formatted markdown following ToC structure.

import logging

from bro_chat.models.document import DocumentMeta
from bro_chat.services.document_store import DocumentStore

logger = logging.getLogger(__name__)


def export_document(store: DocumentStore, meta: DocumentMeta) -> str:
    """Export a vision document as Markdown.

    Args:
        store: Document store instance.
        meta: Document metadata.

    Returns:
        Formatted Markdown string.
    """
    lines = []

    # Document header
    lines.append(f"# {meta.component} {meta.version}")
    lines.append("")
    lines.append("*Component Vision Document*")
    lines.append("")

    # Section 1: Preface
    lines.extend(_export_preface(store, meta))

    # Section 2: Getting Started
    lines.extend(_export_getting_started(store, meta))

    # Section 3: Features
    lines.extend(_export_features(store, meta))

    # Section 5: Entities (dynamic)
    lines.extend(_export_entities(store, meta))

    return "\n".join(lines)


def _export_preface(store: DocumentStore, meta: DocumentMeta) -> list[str]:
    """Export the Preface section."""
    lines = []
    lines.append("## 1. Preface")
    lines.append("")

    content = store.read_section(meta, "01-preface")
    if not content:
        lines.append("*Section not completed*")
        lines.append("")
        return lines

    # About This Guide
    if about := content.get("about_this_guide"):
        lines.append("### 1.1 About This Guide")
        lines.append("")
        lines.append(about)
        lines.append("")

    # Audience
    if audience := content.get("audience"):
        lines.append("### 1.2 Audience")
        lines.append("")
        for item in audience:
            lines.append(f"- {item}")
        lines.append("")

    # Reference Documents
    if refs := content.get("reference_documents"):
        lines.append("### 1.3 Reference Documents")
        lines.append("")
        for ref in refs:
            name = ref.get("name", "")
            url = ref.get("url", "")
            if url:
                lines.append(f"- [{name}]({url})")
            else:
                lines.append(f"- {name}")
        lines.append("")

    # Glossary
    if glossary := content.get("glossary"):
        lines.append("### 1.4 Glossary")
        lines.append("")
        for item in glossary:
            term = item.get("term", "")
            definition = item.get("definition", "")
            lines.append(f"**{term}**: {definition}")
            lines.append("")

    return lines


def _export_getting_started(store: DocumentStore, meta: DocumentMeta) -> list[str]:
    """Export the Getting Started section."""
    lines = []
    lines.append("## 2. Getting Started")
    lines.append("")

    content = store.read_section(meta, "02-getting-started")
    if not content:
        lines.append("*Section not completed*")
        lines.append("")
        return lines

    # Overview
    if overview := content.get("overview"):
        lines.append("### 2.1 Overview")
        lines.append("")
        lines.append(overview)
        lines.append("")

    # Vision
    if vision := content.get("vision"):
        lines.append("### 2.2 Vision")
        lines.append("")
        lines.append(vision)
        lines.append("")

    # Success Metrics
    if metrics := content.get("success_metrics"):
        lines.append("### 2.3 Success Metrics")
        lines.append("")
        for metric in metrics:
            lines.append(f"- {metric}")
        lines.append("")

    return lines


def _export_features(store: DocumentStore, meta: DocumentMeta) -> list[str]:
    """Export the Features section."""
    lines = []
    lines.append("## 3. Features & Business Process")
    lines.append("")

    # 3.1 List of Features
    lines.append("### 3.1 List of Features")
    lines.append("")

    content = store.read_section(meta, "03-01-list-of-features")
    if not content:
        lines.append("*Section not completed*")
        lines.append("")
        return lines

    features = content.get("features", [])
    if features:
        lines.append("| Feature | Description | Priority |")
        lines.append("|---------|-------------|----------|")
        for feature in features:
            name = feature.get("name", "")
            desc = feature.get("description", "")
            priority = feature.get("priority", "").replace("_", " ").title()
            lines.append(f"| {name} | {desc} | {priority} |")
        lines.append("")

    return lines


def _export_entities(store: DocumentStore, meta: DocumentMeta) -> list[str]:
    """Export the Entities section."""
    lines = []
    lines.append("## 5. Entities")
    lines.append("")

    entities = store.list_entities(meta)
    if not entities:
        lines.append("*No entities defined*")
        lines.append("")
        return lines

    for i, entity_name in enumerate(entities, 1):
        section_id = f"05-entity-{entity_name}"
        content = store.read_section(meta, section_id)

        entity_title = content.get("name", entity_name) if content else entity_name
        lines.append(f"### 5.{i} {entity_title}")
        lines.append("")

        if not content:
            lines.append("*Entity not completed*")
            lines.append("")
            continue

        # Description
        if desc := content.get("description"):
            lines.append(desc)
            lines.append("")

        # Purpose
        if purpose := content.get("purpose"):
            lines.append(f"**Purpose**: {purpose}")
            lines.append("")

        # Attributes
        if attributes := content.get("attributes"):
            lines.append("#### Attributes")
            lines.append("")
            lines.append("| Name | Type | Required | Description |")
            lines.append("|------|------|----------|-------------|")
            for attr in attributes:
                name = attr.get("name", "")
                type_ = attr.get("type", "")
                required = "Yes" if attr.get("required") else "No"
                attr_desc = attr.get("description", "")
                lines.append(f"| {name} | {type_} | {required} | {attr_desc} |")
            lines.append("")

        # Relationships
        if relationships := content.get("relationships"):
            lines.append("#### Relationships")
            lines.append("")
            for rel in relationships:
                entity = rel.get("entity", "")
                rel_type = rel.get("type", "")
                rel_desc = rel.get("description", "")
                lines.append(f"- **{entity}** ({rel_type}): {rel_desc}")
            lines.append("")

        # Business Rules
        if rules := content.get("business_rules"):
            lines.append("#### Business Rules")
            lines.append("")
            for rule in rules:
                lines.append(f"- {rule}")
            lines.append("")

    return lines
