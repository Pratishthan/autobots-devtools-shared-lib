# ABOUTME: Unit tests for the batch_invoker module.
# ABOUTME: Covers helpers, result types, and validation without requiring an API key.

import uuid

import pytest

from dynagent.agents.batch import (
    BatchResult,
    RecordResult,
    _build_configs,
    _build_inputs,
    _extract_last_ai_content,
    batch_invoker,
)

# ---------------------------------------------------------------------------
# _build_inputs
# ---------------------------------------------------------------------------


class TestBuildInputs:
    def test_length_matches_records(self):
        records = ["a", "b", "c"]
        result = _build_inputs("coordinator", records)
        assert len(result) == len(records)

    def test_empty_records_returns_empty(self):
        assert _build_inputs("coordinator", []) == []

    def test_each_input_has_user_message(self):
        result = _build_inputs("coordinator", ["hello"])
        assert result[0]["messages"][0]["role"] == "user"

    def test_message_content_matches_record(self):
        records = ["first", "second"]
        result = _build_inputs("coordinator", records)
        assert result[0]["messages"][0]["content"] == "first"
        assert result[1]["messages"][0]["content"] == "second"

    def test_agent_name_propagated(self):
        result = _build_inputs("preface_agent", ["x"])
        assert result[0]["agent_name"] == "preface_agent"

    def test_session_ids_are_unique_valid_uuid4s(self):
        result = _build_inputs("coordinator", ["a", "b", "c"])
        session_ids = [inp["session_id"] for inp in result]
        # All unique
        assert len(set(session_ids)) == 3
        # All valid uuid4
        for sid in session_ids:
            parsed = uuid.UUID(sid)
            assert parsed.version == 4


# ---------------------------------------------------------------------------
# _build_configs
# ---------------------------------------------------------------------------


class TestBuildConfigs:
    def test_length_matches_count(self):
        assert len(_build_configs(5)) == 5

    def test_zero_count_returns_empty(self):
        assert _build_configs(0) == []

    def test_each_has_configurable_thread_id(self):
        configs = _build_configs(3)
        for cfg in configs:
            configurable = cfg.get("configurable")
            assert configurable is not None
            assert "thread_id" in configurable

    def test_thread_ids_are_unique_valid_uuid4s(self):
        configs = _build_configs(4)
        thread_ids = []
        for cfg in configs:
            configurable = cfg.get("configurable")
            assert configurable is not None
            thread_ids.append(configurable["thread_id"])
        assert len(set(thread_ids)) == 4
        for tid in thread_ids:
            parsed = uuid.UUID(tid)
            assert parsed.version == 4


# ---------------------------------------------------------------------------
# _extract_last_ai_content
# ---------------------------------------------------------------------------


class _FakeMessage:
    """Minimal stand-in for a LangChain BaseMessage (mirrors _FakeTool pattern)."""

    def __init__(self, msg_type: str, content: str):
        self.type = msg_type
        self.content = content


class TestExtractLastAiContent:
    def test_dict_messages_normal_case(self):
        state = {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "ai", "content": "hello back"},
            ]
        }
        assert _extract_last_ai_content(state) == "hello back"

    def test_picks_last_ai_when_multiple(self):
        state = {
            "messages": [
                {"role": "ai", "content": "first"},
                {"role": "user", "content": "again"},
                {"role": "ai", "content": "second"},
            ]
        }
        assert _extract_last_ai_content(state) == "second"

    def test_empty_messages_returns_none(self):
        assert _extract_last_ai_content({"messages": []}) is None

    def test_missing_messages_key_returns_none(self):
        assert _extract_last_ai_content({}) is None

    def test_only_user_messages_returns_none(self):
        state = {"messages": [{"role": "user", "content": "alone"}]}
        assert _extract_last_ai_content(state) is None

    def test_role_assistant_alias(self):
        """'assistant' is an alias for 'ai' in LangChain dict messages."""
        state = {"messages": [{"role": "assistant", "content": "via alias"}]}
        assert _extract_last_ai_content(state) == "via alias"

    def test_basemessage_style_objects(self):
        """LangGraph sometimes returns BaseMessage objects instead of dicts."""
        state = {
            "messages": [
                _FakeMessage("user", "q"),
                _FakeMessage("ai", "answer from object"),
            ]
        }
        assert _extract_last_ai_content(state) == "answer from object"

    def test_basemessage_picks_last_ai(self):
        state = {
            "messages": [
                _FakeMessage("ai", "stale"),
                _FakeMessage("user", "nope"),
                _FakeMessage("ai", "fresh"),
            ]
        }
        assert _extract_last_ai_content(state) == "fresh"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class TestRecordResult:
    def test_success_construction(self):
        r = RecordResult(index=0, success=True, output="ok", error=None)
        assert r.success is True
        assert r.output == "ok"
        assert r.error is None

    def test_failure_construction(self):
        r = RecordResult(index=2, success=False, output=None, error="boom")
        assert r.success is False
        assert r.output is None
        assert r.error == "boom"


class TestBatchResult:
    def test_successes_property(self):
        results = [
            RecordResult(0, success=True, output="a", error=None),
            RecordResult(1, success=False, output=None, error="e"),
            RecordResult(2, success=True, output="b", error=None),
        ]
        br = BatchResult(agent_name="coordinator", total=3, results=results)
        assert len(br.successes) == 2
        assert all(r.success for r in br.successes)

    def test_failures_property(self):
        results = [
            RecordResult(0, success=True, output="a", error=None),
            RecordResult(1, success=False, output=None, error="e"),
        ]
        br = BatchResult(agent_name="coordinator", total=2, results=results)
        assert len(br.failures) == 1
        assert br.failures[0].error == "e"

    def test_empty_results(self):
        br = BatchResult(agent_name="coordinator", total=0, results=[])
        assert br.successes == []
        assert br.failures == []


# ---------------------------------------------------------------------------
# batch_invoker validation (no agent creation — fails before that)
# ---------------------------------------------------------------------------


class TestBatchInvokerValidation:
    def test_raises_on_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            batch_invoker("totally_fake_agent", ["hello"])

    def test_raises_on_empty_records(self):
        with pytest.raises(ValueError, match="[Ee]mpty"):
            batch_invoker("coordinator", [])
