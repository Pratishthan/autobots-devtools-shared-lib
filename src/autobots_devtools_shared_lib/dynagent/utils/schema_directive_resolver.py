"""Schema + directive resolver.

Responsible for:
- Loading parent schema JSON docs from one or more paths (common + domain).
-,Deep-merging parents with domain overriding common.
- Applying directive JSON (directives: [...]) via JSON Pointer and x-fbp-pragmas.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer (RFC 6901) against a document.

    Raises ValueError if the pointer cannot be resolved.
    """
    if pointer in ("", "/"):
        return document

    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON Pointer (must start with '/'): {pointer}")

    current = document
    # Split on '/' and ignore the first empty segment
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                index = int(token)
            except ValueError as e:  # pragma: no cover - defensive
                raise ValueError(
                    f"Non-numeric index '{token}' for list in pointer {pointer}"
                ) from e
            try:
                current = current[index]
            except IndexError as e:
                raise ValueError(f"Index '{index}' out of range for pointer {pointer}") from e
        elif isinstance(current, dict):
            if token not in current:
                raise ValueError(f"Key '{token}' not found while resolving pointer {pointer}")
            current = current[token]
        else:  # pragma: no cover - defensive
            raise ValueError(
                f"Cannot traverse into non-container type at token '{token}' for pointer {pointer}"
            )
    return current


def _merge_pragmas(
    target_node: dict[str, Any], pragma_obj: dict[str, list[str]], description: str | None
) -> None:
    """Merge x-fbp-pragmas into the target node in-place."""
    existing_pragmas = target_node.get("x-fbp-pragmas")
    if not isinstance(existing_pragmas, dict):
        existing_pragmas = {}
        target_node["x-fbp-pragmas"] = existing_pragmas

    for scope, items in pragma_obj.items():
        if not isinstance(items, list):  # pragma: no cover - defensive
            logger.warning("Expected list for pragma scope '%s', got %r", scope, items)
            continue
        existing_list = existing_pragmas.get(scope)
        if not isinstance(existing_list, list):
            existing_list = []
            existing_pragmas[scope] = existing_list
        existing_list.extend(items)

    if description:
        # Directive descriptions directly override/define the node description.
        target_node["description"] = description


def _merge_parent_schemas(parent_docs: list[dict]) -> dict:
    """Deep-merge a list of parent schema documents (domain overrides common)."""

    def _merge(a: dict, b: dict) -> dict:
        result: dict = copy.deepcopy(a)
        for key, value in b.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    merged: dict = {}
    for doc in parent_docs:
        merged = _merge(merged, doc)
    return merged


def resolve_parent_with_directives(parent_paths: list[Path], directive_path: Path) -> dict:
    """Load parent schema(s), merge common+domain, then apply directives.

    Args:
        parent_paths: Ordered [common_parent, domain_parent] schema file paths.
        directive_path: Path to directive JSON with a top-level 'directives' array.
    """
    parent_docs: list[dict] = []
    for path in parent_paths:
        if path.exists():
            try:
                with Path.open(path) as f:
                    parent_docs.append(json.load(f))
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in schema {path}: {e}"
                logger.exception(error_msg)
                raise ValueError(error_msg) from e

    if not parent_docs:
        error_msg = f"No parent schema files found at {[str(p) for p in parent_paths]}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    merged_parent = _merge_parent_schemas(parent_docs)

    try:
        with Path.open(directive_path) as f:
            directive_doc = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in directive {directive_path}: {e}"
        logger.exception(error_msg)
        raise ValueError(error_msg) from e

    entries = directive_doc.get("directives", [])
    if not isinstance(entries, list):
        raise ValueError(f"'directives' must be a list in directive file '{directive_path.name}'")

    merged = copy.deepcopy(merged_parent)

    sources = merged.get("x-fbp-directive-sources")
    if not isinstance(sources, list):
        sources = []
        merged["x-fbp-directive-sources"] = sources

    directive_source = {
        "id": directive_doc.get("id", directive_path.stem),
        "title": directive_doc.get("title", directive_path.stem),
    }
    sources.append(directive_source)

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Directive entries must be objects in '{directive_path.name}'")
        if "target" not in entry or "x-fbp-pragmas" not in entry:
            raise ValueError(
                f"Directive entry in '{directive_path.name}' is missing 'target' or 'x-fbp-pragmas': {entry}"
            )
        pointer = entry["target"]
        pragma_obj = entry["x-fbp-pragmas"]
        description = entry.get("description")

        try:
            target_node = _resolve_json_pointer(merged, pointer)
        except ValueError as e:
            error_msg = f"Failed to resolve JSON Pointer '{pointer}' in directive '{directive_path.name}': {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        if not isinstance(pragma_obj, dict):
            raise ValueError(
                f"'x-fbp-pragmas' must be an object in directive '{directive_path.name}' "
                f"for target '{pointer}', got {type(pragma_obj)!r}"
            )

        _merge_pragmas(target_node, pragma_obj, description)

    return merged
