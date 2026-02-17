### Context key resolver

Use-case apps can control how the context store key is derived from agent state by setting a **context key resolver**. Register it at app startup (before creating the agent) so that `get_context`, `set_context`, and `update_context` use your key.

Define a resolver that takes the current agent state and returns a string key, then pass it to `set_context_key_resolver`:

```python
from collections.abc import Mapping
from typing import Any

from autobots_devtools_shared_lib.common.utils.context_utils import set_context_key_resolver

def _resolve_bro_context_key(state: Mapping[str, Any]) -> str:
    user_name = state.get("user_name") or "default"
    return f"{user_name}"

set_context_key_resolver(_resolve_bro_context_key)
```

Ensure any keys you read from `state` (e.g. `user_name`) are present in the agent state: pass them in `input_state` when invoking the agent and add them to the DynAgent state schema if needed.
