"""Service layer for dynagent infrastructure and utilities.

Provides converters, processors, and other utilities used by tools and agents,
including:

* StructuredOutputConverter - convert conversation history to structured output.
* ContextStore - pluggable session-level context persistence.
"""

from autobots_devtools_shared_lib.common.services.context import (
    CacheBackedContextStore,
    ContextConfigError,
    ContextStore,
    DbRepository,
    InMemoryContextStore,
    RedisContextStore,
    get_context_store,
    set_context_store,
)
from autobots_devtools_shared_lib.dynagent.services.structured_converter import (
    StructuredOutputConverter,
)

__all__ = [
    "CacheBackedContextStore",
    "ContextConfigError",
    "ContextStore",
    "DbRepository",
    "InMemoryContextStore",
    "RedisContextStore",
    "StructuredOutputConverter",
    "get_context_store",
    "set_context_store",
]
