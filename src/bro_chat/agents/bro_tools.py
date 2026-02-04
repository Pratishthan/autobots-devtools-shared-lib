# ABOUTME: BRO use-case tools — the 10 document-management tools that BRO registers.
# ABOUTME: Context (component/version) lives in workspace/_doc_context.json, not state.

import json
import logging

from langchain.tools import ToolRuntime, tool

import dynagent.tools.state_tools as state_tools
from bro_chat.models.status import SectionStatus
from bro_chat.services.document_store import DocumentStore
from bro_chat.services.markdown_exporter import export_document
from dynagent.models.state import Dynagent

logger = logging.getLogger(__name__)

# --- DocumentStore factory (monkeypatchable in tests) ---


def _make_store() -> DocumentStore:
    """Default factory — returns a store rooted at vision-docs/."""
    return DocumentStore()


# --- Context helpers (workspace-based, no state pollution) ---

_CONTEXT_FILE = "_doc_context.json"


def _write_context(session_id: str, component: str, version: str) -> None:
    """Persist the active document (component/version) into the session workspace."""
    path = state_tools.WORKSPACE_BASE / session_id / _CONTEXT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"component": component, "version": version}))


def _read_context(session_id: str) -> dict[str, str] | None:
    """Read the active document context from the session workspace."""
    path = state_tools.WORKSPACE_BASE / session_id / _CONTEXT_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text())  # type: ignore[no-any-return]


# --- Core logic helpers (plain-arg, testable without runtime) ---

# Shared error messages (extracted to stay within line-length limits)
_ERR_NO_CONTEXT = (
    "Error: no active document. Use create_document or set_document_context first."
)


def _err_not_on_disk(ctx: dict[str, str]) -> str:
    comp, ver = ctx["component"], ctx["version"]
    return f"Error: active document '{comp}/{ver}' not found on disk."


def _do_create_document(session_id: str, component: str, version: str) -> str:
    store = _make_store()
    store.create_document(component, version)
    _write_context(session_id, component, version)
    return (
        f"Created document '{component}/{version}' and set it as the active document."
    )


def _do_set_document_context(session_id: str, component: str, version: str) -> str:
    store = _make_store()
    doc = store.get_document(component, version)
    if doc is None:
        return f"Error: document '{component}/{version}' does not exist."
    _write_context(session_id, component, version)
    return f"Switched active document to '{component}/{version}'."


def _do_get_document_status(session_id: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    # Build a readable status summary
    lines = [f"Document: {doc.component}/{doc.version}"]
    if doc.sections:
        for sid, smeta in doc.sections.items():
            lines.append(f"  {sid}: {smeta.status.value}")
    else:
        lines.append("  (no sections written yet)")
    if doc.dynamic_items.entities:
        lines.append(f"  Entities: {', '.join(doc.dynamic_items.entities)}")
    return "\n".join(lines)


def _do_list_documents() -> str:
    store = _make_store()
    docs = store.list_documents()
    if not docs:
        return "No documents found."
    return "\n".join(f"  {c}/{v}" for c, v in docs)


def _do_update_section(session_id: str, section_id: str, content: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON content — {e}"
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    store.write_section(doc, section_id, parsed)
    return f"Updated section '{section_id}' in '{doc.component}/{doc.version}'."


def _do_set_section_status(session_id: str, section_id: str, status: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    # Validate status value
    valid_statuses = {s.value for s in SectionStatus}
    if status not in valid_statuses:
        valid_str = ", ".join(sorted(valid_statuses))
        return f"Error: invalid status '{status}'. Valid: {valid_str}"
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    store.update_section_status(doc, section_id, SectionStatus(status))
    return (
        f"Set section '{section_id}' status to '{status}' "
        f"in '{doc.component}/{doc.version}'."
    )


def _do_export_markdown(session_id: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    return export_document(store, doc)


def _do_create_entity(session_id: str, entity_name: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    store.create_entity(doc, entity_name)
    return f"Created entity '{entity_name}' in '{doc.component}/{doc.version}'."


def _do_list_entities(session_id: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    entities = store.list_entities(doc)
    if not entities:
        return "No entities defined in this document."
    return "Entities: " + ", ".join(entities)


def _do_delete_entity(session_id: str, entity_name: str) -> str:
    ctx = _read_context(session_id)
    if ctx is None:
        return _ERR_NO_CONTEXT
    store = _make_store()
    doc = store.get_document(ctx["component"], ctx["version"])
    if doc is None:
        return _err_not_on_disk(ctx)
    if not store.delete_entity(doc, entity_name):
        return (
            f"Error: entity '{entity_name}' not found "
            f"in '{doc.component}/{doc.version}'."
        )
    return f"Deleted entity '{entity_name}' from '{doc.component}/{doc.version}'."


# --- @tool wrappers (read session_id from runtime, delegate to _do_* helpers) ---


@tool
def create_document(
    runtime: ToolRuntime[None, Dynagent], component: str, version: str
) -> str:
    """Create a new vision document and set it as the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_create_document(session_id, component, version)


@tool
def set_document_context(
    runtime: ToolRuntime[None, Dynagent], component: str, version: str
) -> str:
    """Switch the active document to an existing one (errors if missing)."""
    session_id = runtime.state.get("session_id", "default")
    return _do_set_document_context(session_id, component, version)


@tool
def get_document_status(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Get the status of the currently active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_get_document_status(session_id)


@tool
def list_documents() -> str:
    """List all available vision documents."""
    return _do_list_documents()


@tool
def update_section(
    runtime: ToolRuntime[None, Dynagent], section_id: str, content: str
) -> str:
    """Write structured content (JSON string) to a section of the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_update_section(session_id, section_id, content)


@tool
def set_section_status(
    runtime: ToolRuntime[None, Dynagent], section_id: str, status: str
) -> str:
    """Update the status of a section in the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_set_section_status(session_id, section_id, status)


@tool
def export_markdown(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Export the active document as formatted Markdown."""
    session_id = runtime.state.get("session_id", "default")
    return _do_export_markdown(session_id)


@tool
def create_entity(runtime: ToolRuntime[None, Dynagent], entity_name: str) -> str:
    """Create a new entity in the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_create_entity(session_id, entity_name)


@tool
def list_entities(runtime: ToolRuntime[None, Dynagent]) -> str:
    """List all entities in the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_list_entities(session_id)


@tool
def delete_entity(runtime: ToolRuntime[None, Dynagent], entity_name: str) -> str:
    """Delete an entity from the active document."""
    session_id = runtime.state.get("session_id", "default")
    return _do_delete_entity(session_id, entity_name)


# --- Registration entry-points (called once at app startup) ---


def register_bro_tools() -> None:
    """Register all 10 BRO tools into the dynagent usecase pool."""
    from dynagent.tools.tool_registry import register_usecase_tools

    register_usecase_tools(
        [
            create_document,
            set_document_context,
            get_document_status,
            list_documents,
            update_section,
            set_section_status,
            export_markdown,
            create_entity,
            list_entities,
            delete_entity,
        ]
    )
