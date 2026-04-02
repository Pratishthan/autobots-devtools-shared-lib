from __future__ import annotations

import json

import pytest

from autobots_devtools_shared_lib.dynagent.utils.schema_directive_resolver import (
    resolve_parent_with_directives,
)


def test_directive_resolves_through_ref_in_array_items(tmp_path) -> None:
    item_schema = {
        "type": "object",
        "properties": {
            "unitName": {
                "type": "string",
                "description": "Original unit name description.",
            }
        },
    }
    parent_schema = {
        "type": "object",
        "properties": {
            "newOrModified": {
                "type": "array",
                "items": {"$ref": "./item_schema.json"},
            }
        },
    }
    directive = {
        "id": "lpu_directives",
        "title": "LPU Directives",
        "directives": [
            {
                "target": "/properties/newOrModified/items/properties/unitName",
                "x-fbp-pragmas": {"nurture": ["Generate concise, unique unit names."]},
                "description": "Naming guidance from directive.",
            }
        ],
    }

    item_path = tmp_path / "item_schema.json"
    parent_path = tmp_path / "parent.json"
    directive_path = tmp_path / "directive.json"
    item_path.write_text(json.dumps(item_schema))
    parent_path.write_text(json.dumps(parent_schema))
    directive_path.write_text(json.dumps(directive))

    resolved = resolve_parent_with_directives([parent_path], directive_path)

    unit_name_node = resolved["properties"]["newOrModified"]["items"]["properties"]["unitName"]
    assert unit_name_node["description"] == "Naming guidance from directive."
    assert unit_name_node["x-fbp-pragmas"] == {"nurture": ["Generate concise, unique unit names."]}


def test_directive_overrides_description_and_tracks_compact_source(tmp_path) -> None:
    common_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Common description",
            }
        },
    }
    domain_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Domain description",
            }
        },
    }
    directive = {
        "id": "scenario_directives",
        "title": "Scenario Directives",
        "directives": [
            {
                "target": "/properties/name",
                "x-fbp-pragmas": {"nurture": ["Use user-facing names."]},
                "description": "Directive description override",
            }
        ],
    }

    common_path = tmp_path / "common.json"
    domain_path = tmp_path / "domain.json"
    directive_path = tmp_path / "directive.json"
    common_path.write_text(json.dumps(common_schema))
    domain_path.write_text(json.dumps(domain_schema))
    directive_path.write_text(json.dumps(directive))

    resolved = resolve_parent_with_directives([common_path, domain_path], directive_path)

    assert resolved["properties"]["name"]["description"] == "Directive description override"
    assert "x-fbp-pragma-descriptions" not in resolved["properties"]["name"]
    assert resolved["x-fbp-directive-sources"] == [
        {
            "id": "scenario_directives",
            "title": "Scenario Directives",
        }
    ]


def test_missing_directive_file_raises(tmp_path) -> None:
    parent = {"type": "object", "properties": {"a": {"type": "string"}}}
    parent_path = tmp_path / "parent.json"
    parent_path.write_text(json.dumps(parent))
    missing_directive = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError):
        resolve_parent_with_directives([parent_path], missing_directive)


def test_missing_all_parent_files_raises(tmp_path) -> None:
    directive = {"directives": []}
    directive_path = tmp_path / "directive.json"
    directive_path.write_text(json.dumps(directive))

    with pytest.raises(FileNotFoundError, match="No parent schema files found"):
        resolve_parent_with_directives(
            [tmp_path / "missing1.json", tmp_path / "missing2.json"], directive_path
        )


def test_bad_json_pointer_raises(tmp_path) -> None:
    parent = {"type": "object", "properties": {"a": {"type": "string"}}}
    directive = {
        "directives": [
            {
                "target": "/properties/nonexistent/deep",
                "x-fbp-pragmas": {"scope": ["item"]},
            }
        ],
    }
    parent_path = tmp_path / "parent.json"
    directive_path = tmp_path / "directive.json"
    parent_path.write_text(json.dumps(parent))
    directive_path.write_text(json.dumps(directive))

    with pytest.raises(ValueError, match="not found while resolving pointer"):
        resolve_parent_with_directives([parent_path], directive_path)


def test_plain_schema_no_refs(tmp_path) -> None:
    parent = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "A name"},
        },
    }
    directive = {
        "id": "test",
        "title": "Test",
        "directives": [
            {
                "target": "/properties/name",
                "x-fbp-pragmas": {"default": ["Keep it short"]},
                "description": "Overridden",
            }
        ],
    }
    parent_path = tmp_path / "parent.json"
    directive_path = tmp_path / "directive.json"
    parent_path.write_text(json.dumps(parent))
    directive_path.write_text(json.dumps(directive))

    resolved = resolve_parent_with_directives([parent_path], directive_path)
    assert resolved["properties"]["name"]["description"] == "Overridden"
    assert resolved["properties"]["name"]["x-fbp-pragmas"] == {"default": ["Keep it short"]}
