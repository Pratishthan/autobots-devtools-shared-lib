from __future__ import annotations

import json

from autobots_devtools_shared_lib.dynagent.utils.schema_directive_resolver import (
    resolve_parent_with_directives,
)


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
