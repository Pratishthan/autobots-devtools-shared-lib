"""Print resolved input/output schemas and injected prompt.

Run:
    DYNAGENT_CONFIG_ROOT_DIR=configs/sample_domain python -m tests.manual.print_resolved_schemas
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    DynagentSettings,
    set_dynagent_settings,
)


def main() -> None:
    # Default to sample_domain unless caller sets this externally.
    os.environ.setdefault("DYNAGENT_CONFIG_ROOT_DIR", "configs/sample_domain")

    set_dynagent_settings(DynagentSettings())
    AgentMeta.reset()
    meta = AgentMeta.instance()

    agent_name = "logical_agent"

    print("=== Resolved INPUT schemas ===")
    resolved_inputs = meta.input_schema_map.get(agent_name, {})
    for schema_key, schema in resolved_inputs.items():
        print(f"\n--- {schema_key} ---")
        print(json.dumps(schema, indent=2, sort_keys=True))

    print("\n=== Resolved OUTPUT schema ===")
    resolved_output = meta.output_schema_map.get(agent_name)
    if resolved_output is None:
        print("None")
    else:
        print(json.dumps(resolved_output, indent=2, sort_keys=True))

    print("\n=== Prompt after input placeholder injection ===")
    raw_prompt = meta.prompt_map.get(agent_name, "")
    format_values = {
        key: json.dumps(value, indent=2, sort_keys=True) for key, value in resolved_inputs.items()
    }
    print(raw_prompt.format_map(defaultdict(str, **format_values)))


if __name__ == "__main__":
    main()
