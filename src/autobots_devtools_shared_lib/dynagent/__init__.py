# ABOUTME: Root package for the dynagent reference architecture.
# ABOUTME: Provides generic agent orchestration primitives for shared-lib use.
#
# Public API for consumers: import from here for a stable surface.
# UI streaming helpers live in dynagent.ui to avoid pulling Chainlit for
# batch/invoke-only use.

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    get_batch_enabled_agents,
)
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent
from autobots_devtools_shared_lib.dynagent.agents.batch import (
    BatchResult,
    RecordResult,
    batch_invoker,
)
from autobots_devtools_shared_lib.dynagent.agents.invocation_utils import (
    ainvoke_agent,
    invoke_agent,
)
from autobots_devtools_shared_lib.dynagent.llm.llm import lm
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import (
    register_usecase_tools,
)

__all__ = [
    "AgentMeta",
    "BatchResult",
    "Dynagent",
    "RecordResult",
    "ainvoke_agent",
    "batch_invoker",
    "create_base_agent",
    "get_batch_enabled_agents",
    "invoke_agent",
    "lm",
    "register_usecase_tools",
]
