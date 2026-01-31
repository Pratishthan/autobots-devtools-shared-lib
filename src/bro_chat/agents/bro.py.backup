# ABOUTME: Main bro agent for vision document creation.
# ABOUTME: Implements coordinator and section agents following dynagent pattern.

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, NotRequired, cast

from dotenv import load_dotenv
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    SummarizationMiddleware,
    wrap_model_call,
)
from langchain.messages import SystemMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

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
from bro_chat.config.section_config import load_agents_config
from bro_chat.services.document_store import DocumentStore
from bro_chat.utils.files import load_prompt

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


def get_bro_agent_list(
    config_dir: Path = Path("configs/vision-agent"),
) -> list[str]:
    """Return list of available bro agent names from config.

    Args:
        config_dir: Directory containing agents.yaml configuration.

    Returns:
        List of agent names defined in configuration.
    """
    from bro_chat.config.section_config import load_agents_config

    agents_config = load_agents_config(config_dir)
    return list(agents_config.keys())


class BroAgentState(AgentState):
    """State for the bro agent workflow."""

    current_step: NotRequired[str]
    component: NotRequired[str]
    version: NotRequired[str]
    entity_name: NotRequired[str]


def create_error_command(message: str, tool_call_id: str) -> Command:
    """Create a Command for error/validation failure responses."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def create_transition_command(
    message: str, tool_call_id: str, new_step: str, **updates: Any
) -> Command:
    """Create a Command for successful state transitions."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ],
            "current_step": new_step,
            **updates,
        }
    )


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


def build_step_config(
    tool_registry: dict[str, Any],
    config_dir: Path = Path("configs/vision-agent"),
) -> dict[str, dict[str, Any]]:
    """Build step configuration from agents.yaml configuration.

    Args:
        tool_registry: Dictionary mapping tool names to tool objects.
        config_dir: Directory containing agents.yaml configuration.

    Returns:
        Dictionary mapping agent_id to step configuration.
    """

    agents_config = load_agents_config(config_dir)
    step_config = {}

    for agent_id, agent_cfg in agents_config.items():
        # Map tool names to tool objects
        tool_objects = [tool_registry[name] for name in agent_cfg.tools]

        step_config[agent_id] = {
            "prompt": load_prompt(agent_cfg.prompt),
            "tools": tool_objects,
            "requires": [],  # Could also come from config if needed
        }

    return step_config


# Global step config (initialized lazily)
BRO_STEP_CONFIG: dict[str, dict[str, Any]] = {}


def get_step_config(store: DocumentStore) -> dict[str, dict[str, Any]]:
    """Get or create step configuration."""
    global BRO_STEP_CONFIG
    if not BRO_STEP_CONFIG:
        tool_registry = create_bro_tools(store)
        BRO_STEP_CONFIG = build_step_config(tool_registry)
    return BRO_STEP_CONFIG


def create_apply_bro_step_config(store: DocumentStore):
    """Create the step configuration middleware."""
    step_config = get_step_config(store)

    @wrap_model_call  # type: ignore[arg-type]
    async def apply_bro_step_config(
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Configure agent behavior based on the current step."""
        current_step = request.state.get("current_step", "coordinator")
        message_count = len(request.messages)
        logger.info(
            f"Applying bro step config for: {current_step}. Messages: {message_count}"
        )

        stage_config = step_config[current_step]

        # Validate required state
        for key in stage_config["requires"]:
            if request.state.get(key) is None:
                raise ValueError(f"{key} must be set before reaching {current_step}")

        # Format prompt with state values
        format_values = {
            "component": request.state.get("component", ""),
            "version": request.state.get("version", ""),
            "last_section": request.state.get("last_section", ""),
            "entity_name": request.state.get("entity_name", ""),
            "entities_list": "",
        }
        system_prompt = stage_config["prompt"].format(**format_values)

        request = request.override(
            system_message=SystemMessage(content=system_prompt),
            tools=stage_config["tools"],
        )

        return await handler(request)

    return apply_bro_step_config


def create_bro_agent(
    store: DocumentStore | None = None,
    checkpointer: Any = None,
    base_path: Path | str = "vision-docs",
):
    """Create the bro agent with step-based middleware.

    Args:
        store: Document store instance. Created if not provided.
        checkpointer: LangGraph checkpointer for persistence.
        base_path: Base path for document storage.

    Returns:
        Configured bro agent.
    """
    if store is None:
        store = DocumentStore(base_path=base_path)

    if checkpointer is None:
        checkpointer = InMemorySaver()

    step_config = get_step_config(store)
    all_tools = []
    for config in step_config.values():
        all_tools.extend(config["tools"])

    agent = create_agent(
        model,
        name="bro-agent",
        tools=all_tools,
        state_schema=BroAgentState,
        middleware=cast(
            list[AgentMiddleware[Any, Any]],
            [
                create_apply_bro_step_config(store),
                SummarizationMiddleware(
                    model=model,
                    trigger=("fraction", 0.6),
                    keep=("messages", 20),
                ),
            ],
        ),
        checkpointer=checkpointer,
    )

    return agent
