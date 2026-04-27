# ABOUTME: Unit tests for dynadoc render engine.
# ABOUTME: Covers leaf, composite, depth-N, strict and lenient modes.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynadoc import render_document
from autobots_devtools_shared_lib.dynadoc.engine import render_tree
from autobots_devtools_shared_lib.dynadoc.errors import (
    MalformedJsonError,
    MissingInputError,
    MissingTemplateError,
    UndefinedVariableError,
)
from autobots_devtools_shared_lib.dynadoc.manifest import parse_manifest
from tests.unit.dynadoc.conftest import make_json_loader, make_template_loader


def test_leaf_renders_to_md():
    docs = parse_manifest({"documents": {"d": {"json": "a.json", "template": "a.md.j2"}}})
    load_json = make_json_loader({"a.json": {"name": "world"}})
    load_template = make_template_loader({"a.md.j2": "Hello {{ name }}"})

    result = render_tree(docs["d"], load_json, load_template, strict=True)
    assert result.md == "Hello world"
    assert result.errors == []


def test_composite_2_level_concatenates_children():
    docs = parse_manifest(
        {
            "documents": {
                "d": {
                    "template": "outer.md.j2",
                    "children": {
                        "x": {"json": "x.json", "template": "x.md.j2"},
                        "y": {"json": "y.json", "template": "y.md.j2"},
                    },
                }
            }
        }
    )
    load_json = make_json_loader({"x.json": {"v": "X"}, "y.json": {"v": "Y"}})
    load_template = make_template_loader(
        {
            "outer.md.j2": "{{ sections.x }}|{{ sections.y }}",
            "x.md.j2": "x={{ v }}",
            "y.md.j2": "y={{ v }}",
        }
    )

    result = render_tree(docs["d"], load_json, load_template, strict=True)
    assert result.md == "x=X|y=Y"


def test_composite_3_level():
    docs = parse_manifest(
        {
            "documents": {
                "d": {
                    "template": "L0.j2",
                    "children": {
                        "mid": {
                            "template": "L1.j2",
                            "children": {
                                "inner": {"json": "i.json", "template": "L2.j2"},
                            },
                        }
                    },
                }
            }
        }
    )
    load_json = make_json_loader({"i.json": {"v": 42}})
    load_template = make_template_loader(
        {
            "L0.j2": "[{{ sections.mid }}]",
            "L1.j2": "<{{ sections.inner }}>",
            "L2.j2": "v={{ v }}",
        }
    )

    result = render_tree(docs["d"], load_json, load_template, strict=True)
    assert result.md == "[<v=42>]"


# --- strict-mode failure cases ---


def test_strict_missing_json_raises():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({})  # empty
    load_template = make_template_loader({"t.j2": "x"})

    with pytest.raises(MissingInputError, match=r"x\.json"):
        render_tree(docs["d"], load_json, load_template, strict=True)


def test_strict_missing_template_raises():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({"x.json": {}})
    load_template = make_template_loader({})

    with pytest.raises(MissingTemplateError, match=r"t\.j2"):
        render_tree(docs["d"], load_json, load_template, strict=True)


def test_strict_undefined_variable_raises():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({"x.json": {}})
    load_template = make_template_loader({"t.j2": "{{ does_not_exist }}"})

    with pytest.raises(UndefinedVariableError):
        render_tree(docs["d"], load_json, load_template, strict=True)


def test_malformed_json_raises_in_strict_mode():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})

    def bad_loader(_: str) -> dict:
        raise ValueError("bad json")

    load_template = make_template_loader({"t.j2": "ok"})
    with pytest.raises(MalformedJsonError):
        render_tree(docs["d"], bad_loader, load_template, strict=True)


# --- lenient mode ---


def test_lenient_missing_json_yields_placeholder_and_error():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({})
    load_template = make_template_loader({"t.j2": "ignored"})

    result = render_tree(docs["d"], load_json, load_template, strict=False)
    assert result.md == "> _Section pending: d_"
    assert len(result.errors) == 1
    assert result.errors[0].kind == "missing_json"
    assert result.errors[0].node_path == "d"


def test_lenient_missing_template_yields_placeholder():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({"x.json": {}})
    load_template = make_template_loader({})

    result = render_tree(docs["d"], load_json, load_template, strict=False)
    assert result.md == "> _Section pending: d_"
    assert result.errors[0].kind == "missing_template"


def test_lenient_undefined_variable_yields_placeholder():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})
    load_json = make_json_loader({"x.json": {}})
    load_template = make_template_loader({"t.j2": "{{ ghost }}"})

    result = render_tree(docs["d"], load_json, load_template, strict=False)
    assert result.md == "> _Section pending: d_"
    assert result.errors[0].kind == "undefined_variable"


def test_lenient_partial_composite_renders_other_sections():
    docs = parse_manifest(
        {
            "documents": {
                "d": {
                    "template": "outer.md.j2",
                    "children": {
                        "ok": {"json": "ok.json", "template": "ok.j2"},
                        "missing": {"json": "missing.json", "template": "m.j2"},
                    },
                }
            }
        }
    )
    load_json = make_json_loader({"ok.json": {"v": "OK"}})
    load_template = make_template_loader(
        {
            "outer.md.j2": "{{ sections.ok }}/{{ sections.missing }}",
            "ok.j2": "{{ v }}",
            "m.j2": "irrelevant",
        }
    )

    result = render_tree(docs["d"], load_json, load_template, strict=False)
    assert result.md == "OK/> _Section pending: d.missing_"
    assert len(result.errors) == 1
    assert result.errors[0].node_path == "d.missing"


# --- malformed JSON raises in BOTH modes (spec contract) ---


def test_malformed_json_raises_in_lenient_mode():
    docs = parse_manifest({"documents": {"d": {"json": "x.json", "template": "t.j2"}}})

    def bad_loader(_: str) -> dict:
        raise ValueError("bad json")

    load_template = make_template_loader({"t.j2": "ok"})
    with pytest.raises(MalformedJsonError):
        render_tree(docs["d"], bad_loader, load_template, strict=False)


# --- refactor invariance: leaf can become a pass-through subtree ---


def test_leaf_to_passthrough_subtree_yields_identical_output():
    """Replacing a leaf with a composite whose template is `{{ sections.inner }}` is a no-op."""
    leaf_docs = parse_manifest(
        {
            "documents": {
                "d": {
                    "template": "outer.md.j2",
                    "children": {
                        "x": {"json": "x.json", "template": "x.md.j2"},
                    },
                }
            }
        }
    )
    refactored_docs = parse_manifest(
        {
            "documents": {
                "d": {
                    "template": "outer.md.j2",
                    "children": {
                        "x": {
                            "template": "passthrough.j2",
                            "children": {
                                "inner": {"json": "x.json", "template": "x.md.j2"},
                            },
                        }
                    },
                }
            }
        }
    )
    load_json = make_json_loader({"x.json": {"v": "VAL"}})
    load_template = make_template_loader(
        {
            "outer.md.j2": "[{{ sections.x }}]",
            "x.md.j2": "{{ v }}",
            "passthrough.j2": "{{ sections.inner }}",
        }
    )

    leaf_md = render_tree(leaf_docs["d"], load_json, load_template, strict=True).md
    refactored_md = render_tree(refactored_docs["d"], load_json, load_template, strict=True).md
    assert leaf_md == refactored_md == "[VAL]"


# --- public entry point ---


_BRO_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "bro"


def test_render_document_end_to_end(monkeypatch):
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: _BRO_CONFIG,
    )

    def load_json(_: str) -> dict:
        return {"who": "world"}

    result = render_document("smoke_e2e", load_json=load_json, strict=True)
    assert result.md.strip() == "hello world"
    assert result.errors == []
