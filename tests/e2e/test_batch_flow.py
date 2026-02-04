# ABOUTME: End-to-end tests for the batch_invoker full round-trip.
# ABOUTME: bro_registered_e2e (autouse) in conftest handles tool registration.

from dynagent.agents.batch import BatchResult, RecordResult, batch_invoker
from tests.conftest import requires_google_api


@requires_google_api
def test_e2e_batch_full_flow():
    """Full round-trip: structure, content, RecordResult shape."""
    prompts = ["Describe what you do.", "What agents are available?"]
    result = batch_invoker("coordinator", prompts)

    # Top-level structure
    assert isinstance(result, BatchResult)
    assert result.agent_name == "coordinator"
    assert result.total == 2
    assert len(result.results) == 2

    # Per-record shape
    for record in result.results:
        assert isinstance(record, RecordResult)
        assert record.success is True
        assert record.output is not None
        assert len(record.output) > 0
        assert record.error is None


@requires_google_api
def test_e2e_batch_successes_failures_properties():
    """.successes / .failures partition on real data."""
    result = batch_invoker("coordinator", ["Hello there."])
    # With a valid prompt we expect all successes
    assert len(result.successes) == 1
    assert len(result.failures) == 0
    assert result.successes[0].index == 0


@requires_google_api
def test_e2e_batch_single_record_coordinator():
    """Substantive (non-whitespace) response from coordinator."""
    result = batch_invoker("coordinator", ["What is a Component Vision Document?"])
    assert len(result.successes) == 1
    output = result.successes[0].output or ""
    assert output.strip(), "Response must contain non-whitespace content"


@requires_google_api
def test_e2e_batch_across_agents():
    """Sequential batches to coordinator then preface_agent both produce output."""
    coord_result = batch_invoker("coordinator", ["Hi coordinator."])
    preface_result = batch_invoker("preface_agent", ["Hi preface agent."])

    assert len(coord_result.successes) == 1
    assert coord_result.successes[0].output is not None

    assert len(preface_result.successes) == 1
    assert preface_result.successes[0].output is not None
