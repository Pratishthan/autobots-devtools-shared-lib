# ABOUTME: Assertions for files written to the file server workspace by agents.
# ABOUTME: Complements golden_match (structured_response) for agents that output via file tools.
"""written_file_matches assertion evaluator."""

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

# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

FileModeHandler = Any  # (content: str, actual: Any, config: dict, name: str) -> AssertionResult

_MODE_REGISTRY: dict[str, FileModeHandler] = {}


def _register_mode(name: str, fn: FileModeHandler) -> None:
    _MODE_REGISTRY[name] = fn


def _resolve_mode(mode: str, assertion_name: str) -> FileModeHandler | AssertionResult:
    if mode not in _MODE_REGISTRY:
        available = ", ".join(sorted(_MODE_REGISTRY.keys()))
        return AssertionResult(
            passed=False,
            name=assertion_name,
            detail=f"Unknown mode: '{mode}'. Available: {available}",
        )
    return _MODE_REGISTRY[mode]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:\w+)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _read_workspace_file(file_name: str, raw_state: dict[str, Any]) -> str:
    workspace_context = resolve_workspace_context(raw_state)
    content = _read_file(file_name, workspace_context)
    if content.startswith("Error"):
        raise RuntimeError(f"File server read failed for '{file_name}': {content}")
    return content


def _load_json(content: str, assertion_name: str) -> tuple[Any, AssertionResult | None]:
    try:
        return json.loads(_strip_code_fences(content)), None
    except json.JSONDecodeError as e:
        return None, AssertionResult(
            passed=False, name=assertion_name, detail=f"JSON parse error: {e}"
        )


def _load_reference(
    config: dict[str, Any], assertion_name: str
) -> tuple[Any, AssertionResult | None]:
    ref_path_str = config.get("reference")
    if not ref_path_str:
        return None, AssertionResult(
            passed=False,
            name=assertion_name,
            detail=f"Mode '{config.get('mode')}' requires 'reference'",
        )
    ref_path = Path(ref_path_str)
    if not ref_path.exists():
        return None, AssertionResult(
            passed=False, name=assertion_name, detail=f"Reference not found: {ref_path}"
        )
    return json.loads(ref_path.read_text()), None


# ---------------------------------------------------------------------------
# Built-in mode implementations
# ---------------------------------------------------------------------------


def _mode_contains(
    content: str, _actual: Any, config: dict[str, Any], name: str
) -> AssertionResult:
    value = str(config.get("value", ""))
    found = value.lower() in content.lower()
    return AssertionResult(
        passed=found,
        name=name,
        detail=f"{'Found' if found else 'Not found'}: {value!r}",
    )


def _mode_schema(_content: str, actual: Any, config: dict[str, Any], name: str) -> AssertionResult:
    schema_source = config.get("schema")
    if schema_source is None:
        return AssertionResult(
            passed=False, name=name, detail="Mode 'schema' requires 'schema' key"
        )
    try:
        schema: dict[str, Any] = (
            json.loads(Path(str(schema_source)).read_text())
            if isinstance(schema_source, str)
            else schema_source
        )
        js.validate(instance=actual, schema=schema)
        return AssertionResult(passed=True, name=name, detail="Schema valid")
    except js.ValidationError as e:
        return AssertionResult(passed=False, name=name, detail=f"Schema invalid: {e.message}")
    except (FileNotFoundError, OSError) as e:
        return AssertionResult(passed=False, name=name, detail=f"Schema load error: {e}")


def _mode_exact(_content: str, actual: Any, config: dict[str, Any], name: str) -> AssertionResult:
    reference, err = _load_reference(config, name)
    if err:
        return err
    ignore_fields: list[str] = config.get("ignore_fields", [])
    diff = _diff_json(reference, actual, ignore_fields=ignore_fields)
    if diff.has_differences:
        return AssertionResult(passed=False, name=name, detail=diff.to_detail())
    return AssertionResult(passed=True, name=name, detail="Exact match")


def _mode_structural(
    _content: str, actual: Any, config: dict[str, Any], name: str
) -> AssertionResult:
    reference, err = _load_reference(config, name)
    if err:
        return err
    ignore_fields: list[str] = config.get("ignore_fields", [])
    issues = _deep_structural_compare(reference, actual, ignore_fields=ignore_fields)
    if issues:
        return AssertionResult(
            passed=False,
            name=name,
            detail="Structural mismatch:\n" + "\n".join(f"  {i}" for i in issues),
        )
    return AssertionResult(passed=True, name=name, detail="Structural match")


_register_mode("contains", _mode_contains)
_register_mode("schema", _mode_schema)
_register_mode("exact", _mode_exact)
_register_mode("structural", _mode_structural)

# ---------------------------------------------------------------------------
# Core dispatch
# ---------------------------------------------------------------------------

_JSON_MODES = {"schema", "exact", "structural"}


def _single_file_match(
    path: str, config: dict[str, Any], agent_output: AgentOutput
) -> AssertionResult:
    assertion_name = f"written_file_matches:{path}"
    mode = config.get("mode", "schema")

    handler = _resolve_mode(mode, assertion_name)
    if isinstance(handler, AssertionResult):
        return handler

    try:
        content = _read_workspace_file(path, agent_output.raw_state)
    except RuntimeError as e:
        return AssertionResult(passed=False, name=assertion_name, detail=str(e))

    # Modes that need parsed JSON get it up front
    actual: Any = None
    if mode in _JSON_MODES:
        actual, err = _load_json(content, assertion_name)
        if err:
            return err

    return handler(content, actual, config, assertion_name)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


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
