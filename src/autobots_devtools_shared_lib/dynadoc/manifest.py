# ABOUTME: Manifest dataclasses and parser for dynadoc.yaml.
# ABOUTME: Validates leaf-XOR-composite shape and preserves child insertion order.

from dataclasses import dataclass, field
from typing import Any

from autobots_devtools_shared_lib.dynadoc.errors import ManifestValidationError


@dataclass
class Node:
    path: str  # dotted manifest path, e.g. "lld.data.models"
    template: str
    json_path: str | None = None  # leaf only
    children: dict[str, "Node"] = field(default_factory=dict)  # composite only

    def is_leaf(self) -> bool:
        return self.json_path is not None


def _parse_node(raw: Any, path: str) -> Node:
    if not isinstance(raw, dict):
        raise ManifestValidationError(
            f"Node at '{path}' must be a mapping; got {type(raw).__name__}"
        )

    has_json = "json" in raw
    has_children = "children" in raw

    if has_json and has_children:
        raise ManifestValidationError(f"Node at '{path}' cannot have both 'json' and 'children'")
    if not has_json and not has_children:
        raise ManifestValidationError(
            f"Node at '{path}' must have either 'json' (leaf) or 'children' (composite)"
        )
    if "template" not in raw:
        raise ManifestValidationError(f"Node at '{path}' is missing 'template'")

    template = raw["template"]

    if has_json:
        return Node(path=path, template=template, json_path=raw["json"])

    raw_children = raw["children"]
    if not isinstance(raw_children, dict) or not raw_children:
        raise ManifestValidationError(f"Node at '{path}' has empty or non-mapping 'children'")

    children: dict[str, Node] = {}
    for name, child_raw in raw_children.items():  # YAML preserves insertion order
        children[name] = _parse_node(child_raw, f"{path}.{name}")
    return Node(path=path, template=template, children=children)


def parse_manifest(raw: dict) -> dict[str, Node]:
    """Parse the top-level manifest dict (output of yaml.safe_load) into Node trees."""
    documents = raw.get("documents")
    if documents is None:
        raise ManifestValidationError("Manifest must have a top-level 'documents' map")
    if not isinstance(documents, dict):
        raise ManifestValidationError("'documents' must be a mapping")

    return {name: _parse_node(node_raw, name) for name, node_raw in documents.items()}


def find_document(documents: dict[str, Node], name: str) -> Node:
    """Return the document node by top-level name, or raise."""
    if name not in documents:
        raise ManifestValidationError(
            f"Unknown document '{name}'. Available: {sorted(documents.keys())}"
        )
    return documents[name]
