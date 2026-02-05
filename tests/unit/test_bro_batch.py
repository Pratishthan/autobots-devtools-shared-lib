# ABOUTME: Unit tests for the bro_batch service module.
# ABOUTME: Covers BRO_AGENTS pinning, validation, delegation via stub, and logging.

import logging

import pytest

from bro_chat.services.bro_batch import BRO_AGENTS, bro_batch
from dynagent.agents.batch import BatchResult, RecordResult

# ---------------------------------------------------------------------------
# Stub infrastructure (autouse — replaces batch_invoker for every test here)
# ---------------------------------------------------------------------------


def _stub_invoker(agent_name: str, records: list[str]) -> BatchResult:
    """Synthetic stand-in: one success per record, no LLM call."""
    return BatchResult(
        agent_name=agent_name,
        total=len(records),
        results=[
            RecordResult(index=i, success=True, output=f"stub-output-{i}", error=None)
            for i in range(len(records))
        ],
    )


@pytest.fixture(autouse=True)
def _patch_invoker(monkeypatch):
    """Wire the stub into bro_batch's module namespace."""
    monkeypatch.setattr("bro_chat.services.bro_batch.batch_invoker", _stub_invoker)


# ---------------------------------------------------------------------------
# TestBroAgentsList — pins the BRO_AGENTS constant
# ---------------------------------------------------------------------------


class TestBroAgentsList:
    def test_contains_coordinator(self):
        assert "coordinator" in BRO_AGENTS

    def test_contains_all_section_agents(self):
        section_agents = {
            "preface_agent",
            "getting_started_agent",
            "features_agent",
            "entity_agent",
        }
        assert section_agents.issubset(set(BRO_AGENTS))

    def test_length_matches_agents_yaml(self):
        # agents.yaml defines exactly 5 agents owned by BRO
        assert len(BRO_AGENTS) == 5


# ---------------------------------------------------------------------------
# TestAgentNameValidation — rejects non-BRO agents before any LLM call
# ---------------------------------------------------------------------------


class TestAgentNameValidation:
    def test_raises_on_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown BRO agent"):
            bro_batch("totally_fake_agent", ["hello"])

    def test_raises_on_dynagent_only_agent(self):
        # An agent that dynagent might know but BRO does not own
        with pytest.raises(ValueError, match="Unknown BRO agent"):
            bro_batch("some_other_agent", ["hello"])

    def test_error_message_lists_valid_agents(self):
        with pytest.raises(ValueError, match="coordinator"):
            bro_batch("not_a_bro_agent", ["hello"])


# ---------------------------------------------------------------------------
# TestRecordsValidation
# ---------------------------------------------------------------------------


class TestRecordsValidation:
    def test_raises_on_empty_records(self):
        with pytest.raises(ValueError, match="[Ee]mpty"):
            bro_batch("coordinator", [])


# ---------------------------------------------------------------------------
# TestDelegation — stub proves args flow through and result comes back
# ---------------------------------------------------------------------------


class TestDelegation:
    def test_returns_batch_result(self):
        result = bro_batch("coordinator", ["hello"])
        assert isinstance(result, BatchResult)

    def test_agent_name_propagated(self):
        result = bro_batch("coordinator", ["hello"])
        assert result.agent_name == "coordinator"

    def test_total_matches_input_count(self):
        records = ["a", "b", "c"]
        result = bro_batch("coordinator", records)
        assert result.total == 3

    def test_results_length_matches_input_count(self):
        records = ["a", "b"]
        result = bro_batch("coordinator", records)
        assert len(result.results) == 2

    def test_all_records_marked_success_by_stub(self):
        records = ["x", "y", "z"]
        result = bro_batch("coordinator", records)
        assert all(r.success for r in result.results)

    def test_works_with_every_bro_agent(self):
        for agent in BRO_AGENTS:
            result = bro_batch(agent, ["ping"])
            assert result.agent_name == agent
            assert result.total == 1


# ---------------------------------------------------------------------------
# TestLogging — entry/exit messages verified via caplog
# ---------------------------------------------------------------------------


class TestLogging:
    def test_logs_start_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="bro_chat.services.bro_batch"):
            bro_batch("coordinator", ["hello"])
        assert any("bro_batch starting" in rec.message for rec in caplog.records)

    def test_logs_complete_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="bro_chat.services.bro_batch"):
            bro_batch("coordinator", ["hello"])
        assert any("bro_batch complete" in rec.message for rec in caplog.records)

    def test_log_includes_agent_name(self, caplog):
        with caplog.at_level(logging.INFO, logger="bro_chat.services.bro_batch"):
            bro_batch("preface_agent", ["hello"])
        combined = " ".join(rec.message for rec in caplog.records)
        assert "preface_agent" in combined

    def test_log_includes_record_count(self, caplog):
        with caplog.at_level(logging.INFO, logger="bro_chat.services.bro_batch"):
            bro_batch("coordinator", ["a", "b", "c"])
        # The start log should mention the count 3
        start_msgs = [
            rec.message for rec in caplog.records if "bro_batch starting" in rec.message
        ]
        assert len(start_msgs) == 1
        assert "3" in start_msgs[0]
