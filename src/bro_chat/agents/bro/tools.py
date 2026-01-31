# ABOUTME: LangChain tool wrappers for bro agent.
# ABOUTME: Creates tool instances bound to DocumentStore for vision document operations.

import logging
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from bro_chat.agents.bro.state import (
    BroAgentState,
    create_error_command,
    create_transition_command,
    get_bro_agent_list,
)
from bro_chat.agents.bro_tools import (
    create_bro_document,
    create_bro_entity,
    delete_bro_entity,
    export_bro_markdown,
    get_bro_document_status,
    list_bro_documents,
    list_bro_entities,
    set_bro_section_status,
    update_bro_section,
)
from bro_chat.services.document_store import DocumentStore

logger = logging.getLogger(__name__)


def create_bro_tools(store: DocumentStore) -> dict[str, Any]:
    """Create LangChain tools bound to a document store."""

    @tool
    def handoff(runtime: ToolRuntime[None, BroAgentState], next_agent: str) -> Command:
        """Transition to a different section agent."""
        # Runtime validation
        valid_agents = get_bro_agent_list()
        if next_agent not in valid_agents:
            return create_error_command(
                f"Invalid agent: {next_agent}. Valid agents: {', '.join(valid_agents)}",
                runtime.tool_call_id or "unknown",
            )

        logger.info(f"Handoff Tool called: {next_agent}")
        return create_transition_command(
            f"Handoff to {next_agent}",
            runtime.tool_call_id or "unknown",
            new_step=next_agent,
        )

    @tool
    def set_document_context(
        runtime: ToolRuntime[None, BroAgentState], component: str, version: str
    ) -> Command:
        """Set the document context (component and version) for this session."""
        logger.info(f"Setting document context: {component}/{version}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Document context set to {component}/{version}",
                        tool_call_id=runtime.tool_call_id or "unknown",
                    )
                ],
                "component": component,
                "version": version,
            }
        )

    @tool
    def get_document_status(component: str, version: str) -> str:
        """Get the status of all sections in a vision document."""
        return get_bro_document_status(store, component, version)

    @tool
    def list_documents() -> str:
        """List all available vision documents."""
        return list_bro_documents(store)

    @tool
    def create_document(component: str, version: str) -> str:
        """Create a new vision document."""
        return create_bro_document(store, component, version)

    @tool
    def update_section(
        component: str, version: str, section_id: str, content: dict[str, Any]
    ) -> str:
        """Update section content in a vision document."""
        return update_bro_section(store, component, version, section_id, content)

    @tool
    def set_section_status(
        component: str, version: str, section_id: str, status: str
    ) -> str:
        """Set the status of a section."""
        return set_bro_section_status(store, component, version, section_id, status)

    @tool
    def create_entity(component: str, version: str, entity_name: str) -> str:
        """Create a new entity in the vision document."""
        return create_bro_entity(store, component, version, entity_name)

    @tool
    def list_entities(component: str, version: str) -> str:
        """List all entities in a vision document."""
        return list_bro_entities(store, component, version)

    @tool
    def delete_entity(component: str, version: str, entity_name: str) -> str:
        """Delete an entity from the vision document."""
        return delete_bro_entity(store, component, version, entity_name)

    @tool
    def export_markdown(component: str, version: str) -> str:
        """Export the vision document as Markdown."""
        return export_bro_markdown(store, component, version)

    return {
        "handoff": handoff,
        "set_document_context": set_document_context,
        "get_document_status": get_document_status,
        "list_documents": list_documents,
        "create_document": create_document,
        "update_section": update_section,
        "set_section_status": set_section_status,
        "create_entity": create_entity,
        "list_entities": list_entities,
        "delete_entity": delete_entity,
        "export_markdown": export_markdown,
    }
