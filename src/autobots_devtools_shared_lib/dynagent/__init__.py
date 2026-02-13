# ABOUTME: Root package for the dynagent reference architecture.
# ABOUTME: Provides generic agent orchestration primitives for shared-lib use.
#
# Public API for consumers: import from here for a stable surface.
# UI streaming helpers live in dynagent.ui to avoid pulling Chainlit for
# batch/invoke-only use.

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

__all__ = [
    "BatchResult",
    "RecordResult",
    "ainvoke_agent",
    "batch_invoker",
    "create_base_agent",
    "invoke_agent",
    "lm",
]
