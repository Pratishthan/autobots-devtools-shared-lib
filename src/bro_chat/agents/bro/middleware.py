# ABOUTME: Middleware factory for bro agent step configuration.
# ABOUTME: Applies step-specific prompts and tools based on current workflow state.

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.messages import SystemMessage

from bro_chat.agents.bro.config import get_step_config
from bro_chat.services.document_store import DocumentStore

logger = logging.getLogger(__name__)


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
