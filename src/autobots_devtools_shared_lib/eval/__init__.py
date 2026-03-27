# ABOUTME: Public API for the dynagent eval framework.
# ABOUTME: Import from here for a stable surface — loader, models, and result types.

from autobots_devtools_shared_lib.eval.assertions.registry import register_assertion
from autobots_devtools_shared_lib.eval.core.loader import EvalConfigError, load_eval_cases
from autobots_devtools_shared_lib.eval.models.eval_case import EvalCase
from autobots_devtools_shared_lib.eval.models.result import (
    AgentOutput,
    AssertionResult,
    CostDelta,
    EvalCostSnapshot,
    EvalResult,
    TurnResult,
)

__all__ = [
    "AgentOutput",
    "AssertionResult",
    "CostDelta",
    "EvalCase",
    "EvalConfigError",
    "EvalCostSnapshot",
    "EvalResult",
    "TurnResult",
    "load_eval_cases",
    "register_assertion",
]
