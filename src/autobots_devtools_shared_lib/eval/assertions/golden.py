# ABOUTME: Golden match assertion for comparing agent structured_response against reference files.
# ABOUTME: Supports exact diff mode and structural-only comparison with field ignoring.
"""Golden match assertion: compare agent output against reference files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult


@dataclass
class JsonDiff:
    """Structured diff between reference and actual JSON."""

    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.missing or self.unexpected or self.changed)

    def to_detail(self) -> str:
        lines = [f"Missing from actual: {m}" for m in self.missing]
        lines.extend(f"Unexpected in actual: {u}" for u in self.unexpected)
        lines.extend(f"Changed: {c}" for c in self.changed)
        return "\n".join(lines)


def _diff_json(reference: Any, actual: Any, path: str = "") -> JsonDiff:
    """Recursive deep diff between two JSON-like structures."""
    diff = JsonDiff()

    if isinstance(reference, dict) and isinstance(actual, dict):
        for key in reference:
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                diff.missing.append(f"{child_path}: {json.dumps(reference[key])}")
            else:
                child = _diff_json(reference[key], actual[key], child_path)
                diff.missing.extend(child.missing)
                diff.unexpected.extend(child.unexpected)
                diff.changed.extend(child.changed)
        for key in actual:
            child_path = f"{path}.{key}" if path else key
            if key not in reference:
                diff.unexpected.append(f"{child_path}: {json.dumps(actual[key])}")

    elif isinstance(reference, list) and isinstance(actual, list):
        for i in range(max(len(reference), len(actual))):
            child_path = f"{path}[{i}]"
            if i >= len(actual):
                diff.missing.append(f"{child_path}: {json.dumps(reference[i])}")
            elif i >= len(reference):
                diff.unexpected.append(f"{child_path}: {json.dumps(actual[i])}")
            else:
                child = _diff_json(reference[i], actual[i], child_path)
                diff.missing.extend(child.missing)
                diff.unexpected.extend(child.unexpected)
                diff.changed.extend(child.changed)

    elif reference != actual:
        diff.changed.append(f"{path}: {json.dumps(reference)} → {json.dumps(actual)}")

    return diff


def _deep_structural_compare(
    reference: Any,
    actual: Any,
    path: str = "",
    ignore_fields: list[str] | None = None,
) -> list[str]:
    """Compare structure only: same keys, same types, same array lengths. Ignores string values."""
    ignore = set(ignore_fields or [])
    issues: list[str] = []

    if isinstance(reference, dict) and isinstance(actual, dict):
        for key in reference:
            if key in ignore:
                continue
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                issues.append(f"Missing key: {child_path}")
            else:
                issues.extend(
                    _deep_structural_compare(reference[key], actual[key], child_path, ignore_fields)
                )
        for key in actual:
            if key in ignore:
                continue
            child_path = f"{path}.{key}" if path else key
            if key not in reference:
                issues.append(f"Unexpected key: {child_path}")

    elif isinstance(reference, list) and isinstance(actual, list):
        if len(reference) != len(actual):
            issues.append(
                f"Array length mismatch at {path or 'root'}: "
                f"expected {len(reference)}, got {len(actual)}"
            )
        for i in range(min(len(reference), len(actual))):
            child_path = f"{path}[{i}]"
            issues.extend(
                _deep_structural_compare(reference[i], actual[i], child_path, ignore_fields)
            )

    elif type(reference) is not type(actual):
        issues.append(
            f"Type mismatch at {path or 'root'}: "
            f"expected {type(reference).__name__}, got {type(actual).__name__}"
        )

    return issues


def golden_match(output: AgentOutput, config: Any) -> AssertionResult:
    """Compare agent structured_response against a golden reference file."""
    ref_path = Path(config["reference"])
    mode: str = config.get("mode", "exact")
    ignore_fields: list[str] = config.get("ignore_fields", [])

    if not ref_path.exists():
        return AssertionResult(
            passed=False,
            name="golden_match",
            detail=f"Reference file not found: {ref_path}. Run with --update-golden to create.",
        )

    reference = json.loads(ref_path.read_text())
    actual = output.structured_response

    if mode == "exact":
        diff = _diff_json(reference, actual)
        if diff.has_differences:
            return AssertionResult(
                passed=False,
                name="golden_match",
                detail=f"Reference: {ref_path}\n\n{diff.to_detail()}",
            )
        return AssertionResult(passed=True, name="golden_match", detail="Exact match")

    if mode == "structural":
        issues = _deep_structural_compare(reference, actual, ignore_fields=ignore_fields)
        if issues:
            return AssertionResult(
                passed=False,
                name="golden_match",
                detail="Structural mismatch:\n" + "\n".join(f"  {i}" for i in issues),
            )
        return AssertionResult(passed=True, name="golden_match", detail="Structural match")

    return AssertionResult(
        passed=False,
        name="golden_match",
        detail=f"Unknown mode: {mode}. Use 'exact' or 'structural'.",
    )
