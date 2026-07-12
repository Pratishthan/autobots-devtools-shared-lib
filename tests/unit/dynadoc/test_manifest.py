# ABOUTME: Unit tests for the dynadoc manifest parser.
# ABOUTME: Validates leaf/composite shape rules and tree structure.

import pytest

from autobots_devtools_shared_lib.dynadoc.errors import ManifestValidationError
from autobots_devtools_shared_lib.dynadoc.manifest import (
    find_document,
    parse_manifest,
)


def test_parse_leaf():
    raw = {"documents": {"d": {"json": "a.json", "template": "a.md.j2"}}}
    docs = parse_manifest(raw)
    node = docs["d"]
    assert node.is_leaf()
    assert node.json_path == "a.json"
    assert node.template == "a.md.j2"
    assert node.children == {}


def test_leaf_carries_its_title():
    """A title lets a caller name a node without re-declaring the tree beside the manifest."""
    raw = {"documents": {"d": {"title": "Data Models", "json": "a.json", "template": "a.md.j2"}}}
    assert parse_manifest(raw)["d"].title == "Data Models"


def test_composite_carries_its_title():
    raw = {
        "documents": {
            "d": {
                "title": "Low-Level Design",
                "template": "wrap.md.j2",
                "children": {"x": {"json": "x.json", "template": "x.md.j2"}},
            }
        }
    }
    assert parse_manifest(raw)["d"].title == "Low-Level Design"


def test_title_is_optional():
    """Manifests authored before titles existed still parse."""
    raw = {"documents": {"d": {"json": "a.json", "template": "a.md.j2"}}}
    assert parse_manifest(raw)["d"].title is None


def test_parse_composite_2_level():
    raw = {
        "documents": {
            "d": {
                "template": "wrap.md.j2",
                "children": {
                    "x": {"json": "x.json", "template": "x.md.j2"},
                    "y": {"json": "y.json", "template": "y.md.j2"},
                },
            }
        }
    }
    docs = parse_manifest(raw)
    node = docs["d"]
    assert not node.is_leaf()
    assert list(node.children.keys()) == ["x", "y"]  # insertion order
    assert node.children["x"].is_leaf()


def test_parse_composite_n_level():
    raw = {
        "documents": {
            "d": {
                "template": "outer.md.j2",
                "children": {
                    "mid": {
                        "template": "mid.md.j2",
                        "children": {
                            "inner": {"json": "i.json", "template": "i.md.j2"},
                        },
                    }
                },
            }
        }
    }
    docs = parse_manifest(raw)
    inner = docs["d"].children["mid"].children["inner"]
    assert inner.is_leaf()


def test_mixed_node_rejected():
    raw = {
        "documents": {
            "d": {
                "json": "a.json",
                "template": "a.md.j2",
                "children": {"x": {"json": "x.json", "template": "x.md.j2"}},
            }
        }
    }
    with pytest.raises(ManifestValidationError, match="cannot have both"):
        parse_manifest(raw)


def test_leaf_missing_template_rejected():
    raw = {"documents": {"d": {"json": "a.json"}}}
    with pytest.raises(ManifestValidationError):
        parse_manifest(raw)


def test_composite_missing_template_rejected():
    raw = {"documents": {"d": {"children": {"x": {"json": "x.json", "template": "x.md.j2"}}}}}
    with pytest.raises(ManifestValidationError):
        parse_manifest(raw)


def test_empty_node_rejected():
    raw = {"documents": {"d": {}}}
    with pytest.raises(ManifestValidationError):
        parse_manifest(raw)


def test_find_document_returns_node():
    raw = {"documents": {"d": {"json": "a.json", "template": "a.md.j2"}}}
    docs = parse_manifest(raw)
    node = find_document(docs, "d")
    assert node is docs["d"]


def test_find_document_unknown_raises():
    docs = parse_manifest({"documents": {}})
    with pytest.raises(ManifestValidationError, match="Unknown document"):
        find_document(docs, "missing")


def test_node_path_tracks_dotted_address():
    raw = {
        "documents": {
            "d": {
                "template": "outer.md.j2",
                "children": {"x": {"json": "x.json", "template": "x.md.j2"}},
            }
        }
    }
    docs = parse_manifest(raw)
    assert docs["d"].path == "d"
    assert docs["d"].children["x"].path == "d.x"
