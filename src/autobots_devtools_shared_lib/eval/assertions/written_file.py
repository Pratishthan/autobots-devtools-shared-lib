# ABOUTME: Assertions for files written to the file server workspace by agents.
# ABOUTME: Complements golden_match (structured_response) for agents that output via file tools.
"""written_file_matches / written_files_match assertion evaluators."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema as js

from autobots_devtools_shared_lib.common.utils.fserver_client_utils import read_file as _read_file
from autobots_devtools_shared_lib.eval.assertions.golden import _deep_structural_compare, _diff_json
from autobots_devtools_shared_lib.eval.core.workspace import resolve_workspace_context
from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ``` or ``` ... ```) from text."""
    match = re.search(r"```(?:\w+)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _read_workspace_file(file_name: str, raw_state: dict[str, Any]) -> str:
    """Read a file from the file server using workspace context from the registered provider."""
    workspace_context = resolve_workspace_context(raw_state)
    content = _read_file(file_name, workspace_context)
    if content.startswith("Error"):
        raise RuntimeError(f"File server read failed for '{file_name}': {content}")
    return content


def _single_file_match(
    path: str, config: dict[str, Any], agent_output: AgentOutput
) -> AssertionResult:
    assertion_name = f"written_file_matches:{path}"
    mode = config.get("mode", "schema")

    try:
        content = _read_workspace_file(path, agent_output.raw_state)
    except RuntimeError as e:
        return AssertionResult(passed=False, name=assertion_name, detail=str(e))

    if mode == "contains":
        value = str(config.get("value", ""))
        found = value.lower() in content.lower()
        return AssertionResult(
            passed=found,
            name=assertion_name,
            detail=f"{'Found' if found else 'Not found'}: {value!r}",
        )

    # All remaining modes require valid JSON
    try:
        actual = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as e:
        return AssertionResult(passed=False, name=assertion_name, detail=f"JSON parse error: {e}")

    ignore_fields: list[str] = config.get("ignore_fields", [])

    if mode == "schema":
        schema_source = config.get("schema")
        if schema_source is None:
            return AssertionResult(
                passed=False, name=assertion_name, detail="Mode 'schema' requires 'schema' key"
            )
        try:
            schema: dict[str, Any] = (
                json.loads(Path(str(schema_source)).read_text())
                if isinstance(schema_source, str)
                else schema_source
            )
            js.validate(instance=actual, schema=schema)
            return AssertionResult(passed=True, name=assertion_name, detail="Schema valid")
        except js.ValidationError as e:
            return AssertionResult(
                passed=False, name=assertion_name, detail=f"Schema invalid: {e.message}"
            )
        except (FileNotFoundError, OSError) as e:
            return AssertionResult(
                passed=False, name=assertion_name, detail=f"Schema load error: {e}"
            )

    # exact and structural both need a reference file
    ref_path_str = config.get("reference")
    if not ref_path_str:
        return AssertionResult(
            passed=False, name=assertion_name, detail=f"Mode '{mode}' requires 'reference'"
        )
    ref_path = Path(ref_path_str)
    if not ref_path.exists():
        return AssertionResult(
            passed=False, name=assertion_name, detail=f"Reference not found: {ref_path}"
        )
    reference = json.loads(ref_path.read_text())

    if mode == "exact":
        diff = _diff_json(reference, actual, ignore_fields=ignore_fields)
        if diff.has_differences:
            return AssertionResult(passed=False, name=assertion_name, detail=diff.to_detail())
        return AssertionResult(passed=True, name=assertion_name, detail="Exact match")

    if mode == "structural":
        issues = _deep_structural_compare(reference, actual, ignore_fields=ignore_fields)
        if issues:
            return AssertionResult(
                passed=False,
                name=assertion_name,
                detail="Structural mismatch:\n" + "\n".join(f"  {i}" for i in issues),
            )
        return AssertionResult(passed=True, name=assertion_name, detail="Structural match")

    return AssertionResult(
        passed=False,
        name=assertion_name,
        detail=f"Unknown mode: {mode}. Use schema/exact/structural/contains.",
    )


def written_file_matches(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Assert one or more workspace files match expected content/structure.

    Config can be a single dict or a list of dicts. All entries must pass.

    YAML config keys (per entry):
        path (str): Workspace-relative file path (required).
        mode (str): schema | exact | structural | contains (default: schema).
        schema (str): Path to JSON schema file (mode=schema).
        reference (str): Path to golden reference file (mode=exact|structural).
        ignore_fields (list[str]): Keys to skip at any dict level (mode=exact|structural).
        value (str): Substring to search for (mode=contains).
    """
    if isinstance(config, list):
        entries = config
    elif isinstance(config, dict):
        entries = [config]
    else:
        return AssertionResult(
            passed=False, name="written_file_matches", detail="Config must be a dict or list"
        )

    results = [_single_file_match(entry.get("path", ""), entry, agent_output) for entry in entries]
    failures = [r for r in results if not r.passed]
    if failures:
        if len(entries) == 1:
            return failures[0]
        return AssertionResult(
            passed=False,
            name="written_file_matches",
            detail="\n".join(f"{r.name}: {r.detail}" for r in failures),
        )
    if len(entries) == 1:
        return results[0]
    return AssertionResult(
        passed=True,
        name="written_file_matches",
        detail=f"All {len(results)} files matched",
    )
