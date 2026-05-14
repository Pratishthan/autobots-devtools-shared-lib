# ABOUTME: UI subpackage for the dynagent reference architecture.
# ABOUTME: Shared streaming helpers and a generic Chainlit entry point.

from autobots_devtools_shared_lib.dynagent.ui.approval_gate import (
    ProposalOutcome,
    ask_approval,
    format_unified_diff,
    post_diff_message,
    propose_change,
)
from autobots_devtools_shared_lib.dynagent.ui.ui_utils import (
    format_dict_item,
    stream_agent_events,
    structured_to_markdown,
)

__all__ = [
    "ProposalOutcome",
    "ask_approval",
    "format_dict_item",
    "format_unified_diff",
    "post_diff_message",
    "propose_change",
    "stream_agent_events",
    "structured_to_markdown",
]
