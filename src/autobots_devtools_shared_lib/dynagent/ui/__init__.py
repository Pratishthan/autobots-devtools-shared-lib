# ABOUTME: UI subpackage for the dynagent reference architecture.
# ABOUTME: Shared streaming helpers and a generic Chainlit entry point.

from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app
from autobots_devtools_shared_lib.dynagent.ui.ui_utils import (
    format_dict_item,
    stream_agent_events,
    structured_to_markdown,
)

__all__ = [
    "create_copilotkit_app",
    "format_dict_item",
    "stream_agent_events",
    "structured_to_markdown",
]
