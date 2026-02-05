# ABOUTME: BRO-scoped batch entry point — validates against BRO's agent set.
# ABOUTME: Delegates to dynagent's batch_invoker after the BRO gate passes.

import logging

from dynagent.agents.batch import BatchResult, batch_invoker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BRO ownership declaration (static, not loaded from agents.yaml)
# ---------------------------------------------------------------------------
# A dynamic load would silently expand the gate if non-BRO agents are added
# to agents.yaml.  Keep this list in sync manually — the unit-test canary
# (TestBroAgentsList.test_length_matches_agents_yaml) will scream if it drifts.

BRO_AGENTS: list[str] = [
    "coordinator",
    "preface_agent",
    "getting_started_agent",
    "features_agent",
    "entity_agent",
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def bro_batch(agent_name: str, records: list[str]) -> BatchResult:
    """Run a batch through dynagent, gated to BRO-owned agents only.

    Args:
        agent_name: Must be one of BRO_AGENTS.
        records:    Non-empty list of plain-string prompts.

    Returns:
        BatchResult forwarded from batch_invoker.

    Raises:
        ValueError: If agent_name is not in BRO_AGENTS or records is empty.
    """
    # --- BRO gate (stricter than batch_invoker's own validation) ---
    if agent_name not in BRO_AGENTS:
        raise ValueError(
            f"Unknown BRO agent: {agent_name}. "
            f"Valid agents: {', '.join(BRO_AGENTS)}"
        )

    # --- Records validation ---
    if not records:
        raise ValueError("records must not be empty")

    # --- Entry log (lazy interpolation — avoids ruff G004) ---
    logger.info("bro_batch starting: agent=%s records=%d", agent_name, len(records))

    # --- Delegate to generic batch infrastructure ---
    result = batch_invoker(agent_name, records)

    # --- Exit log ---
    logger.info(
        "bro_batch complete: agent=%s successes=%d failures=%d",
        agent_name,
        len(result.successes),
        len(result.failures),
    )

    return result


# ---------------------------------------------------------------------------
# Manual smoke runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from bro_chat.agents.bro_tools import register_bro_tools

    register_bro_tools()

    smoke_prompts = [
        "What is a Component Vision Document and how do I create one?",
        "Walk me through the preface section of a vision document.",
        "What agents are available in this system?",
    ]

    batch_result = bro_batch("coordinator", smoke_prompts)
    for record in batch_result.results:
        if record.success:
            print(f"Record {record.index} succeeded:\n{record.output}\n")
        else:
            print(f"Record {record.index} failed:\n{record.error}\n")
