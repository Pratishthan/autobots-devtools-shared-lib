# ABOUTME: Tests for golden match assertion.
# ABOUTME: Covers _diff_json, _deep_structural_compare, and golden_match with exact + structural modes.
import json

from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.eval.assertions.golden import (
    _deep_structural_compare,
    _diff_json,
    golden_match,
)
from autobots_devtools_shared_lib.eval.models.result import AgentOutput


def _make_output(structured: dict | None = None) -> AgentOutput:
    return AgentOutput(
        messages=[HumanMessage(content="test"), AIMessage(content="done")],
        structured_response=structured,
        agent_name="test-agent",
        raw_state={},
    )


class TestDiffJson:
    def test_identical(self):
        diff = _diff_json({"a": 1}, {"a": 1})
        assert diff.missing == []
        assert diff.unexpected == []
        assert diff.changed == []

    def test_missing_key(self):
        diff = _diff_json({"a": 1, "b": 2}, {"a": 1})
        assert len(diff.missing) == 1
        assert "b" in diff.missing[0]

    def test_unexpected_key(self):
        diff = _diff_json({"a": 1}, {"a": 1, "b": 2})
        assert len(diff.unexpected) == 1

    def test_changed_value(self):
        diff = _diff_json({"a": 1}, {"a": 2})
        assert len(diff.changed) == 1

    def test_nested_array_diff(self):
        ref = {"models": [{"name": "A"}, {"name": "B"}]}
        actual = {"models": [{"name": "A"}, {"name": "C"}]}
        diff = _diff_json(ref, actual)
        assert len(diff.changed) > 0


class TestDeepStructuralCompare:
    def test_same_structure(self):
        ref = {"models": [{"name": "Party", "type": "entity"}]}
        actual = {"models": [{"name": "Other", "type": "value"}]}
        issues = _deep_structural_compare(ref, actual)
        assert issues == []

    def test_missing_key(self):
        ref = {"models": [{"name": "Party", "type": "entity"}]}
        actual = {"models": [{"name": "Party"}]}
        issues = _deep_structural_compare(ref, actual)
        assert len(issues) > 0

    def test_different_array_length(self):
        ref = {"models": [{"name": "A"}, {"name": "B"}]}
        actual = {"models": [{"name": "A"}]}
        issues = _deep_structural_compare(ref, actual)
        assert len(issues) > 0

    def test_type_mismatch(self):
        ref = {"count": 5}
        actual = {"count": "five"}
        issues = _deep_structural_compare(ref, actual)
        assert len(issues) > 0

    def test_ignore_fields(self):
        ref = {"name": "Party", "description": "A party entity"}
        actual = {"name": "Party", "description": "Something else entirely"}
        issues = _deep_structural_compare(ref, actual, ignore_fields=["description"])
        assert issues == []


class TestGoldenMatch:
    def test_exact_pass(self, tmp_path):
        golden = {"models": [{"name": "Party"}]}
        ref_file = tmp_path / "golden.json"
        ref_file.write_text(json.dumps(golden))

        output = _make_output(structured={"models": [{"name": "Party"}]})
        config = {"reference": str(ref_file), "mode": "exact"}
        r = golden_match(output, config)
        assert r.passed is True

    def test_exact_fail(self, tmp_path):
        golden = {"models": [{"name": "Party"}]}
        ref_file = tmp_path / "golden.json"
        ref_file.write_text(json.dumps(golden))

        output = _make_output(structured={"models": [{"name": "Contact"}]})
        config = {"reference": str(ref_file), "mode": "exact"}
        r = golden_match(output, config)
        assert r.passed is False
        assert "Contact" in r.detail or "Party" in r.detail

    def test_structural_pass_different_values(self, tmp_path):
        golden = {"models": [{"name": "Party", "type": "entity"}]}
        ref_file = tmp_path / "golden.json"
        ref_file.write_text(json.dumps(golden))

        output = _make_output(structured={"models": [{"name": "Other", "type": "value_object"}]})
        config = {"reference": str(ref_file), "mode": "structural"}
        r = golden_match(output, config)
        assert r.passed is True

    def test_structural_fail_missing_key(self, tmp_path):
        golden = {"models": [{"name": "Party", "type": "entity"}]}
        ref_file = tmp_path / "golden.json"
        ref_file.write_text(json.dumps(golden))

        output = _make_output(structured={"models": [{"name": "Party"}]})
        config = {"reference": str(ref_file), "mode": "structural"}
        r = golden_match(output, config)
        assert r.passed is False

    def test_structural_with_ignore_fields(self, tmp_path):
        golden = {"name": "Party", "description": "Original desc"}
        ref_file = tmp_path / "golden.json"
        ref_file.write_text(json.dumps(golden))

        output = _make_output(structured={"name": "Party", "description": "New desc"})
        config = {
            "reference": str(ref_file),
            "mode": "structural",
            "ignore_fields": ["description"],
        }
        r = golden_match(output, config)
        assert r.passed is True

    def test_missing_reference_file(self):
        output = _make_output(structured={"a": 1})
        config = {"reference": "/nonexistent/path.json", "mode": "exact"}
        r = golden_match(output, config)
        assert r.passed is False
        assert "not found" in r.detail.lower() or "update-golden" in r.detail.lower()
