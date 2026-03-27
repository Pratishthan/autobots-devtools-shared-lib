# ABOUTME: Singleton registry of MCP server definitions (bundled + usecase).
# ABOUTME: Use-case servers override bundled ones by name.

import threading

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig

logger = get_logger(__name__)

_instance: "McpServerRegistry | None" = None
_lock = threading.Lock()


class McpServerRegistry:
    """Holds MCP server definitions from bundled (shared-lib) and usecase sources."""

    def __init__(self) -> None:
        from autobots_devtools_shared_lib.dynagent.mcp.servers import BUNDLED_SERVERS

        self._bundled: dict[str, McpServerConfig] = {s.name: s for s in BUNDLED_SERVERS}
        self._usecase: dict[str, McpServerConfig] = {}
        logger.info("McpServerRegistry initialized with bundled: %s", list(self._bundled.keys()))

    @classmethod
    def instance(cls) -> "McpServerRegistry":
        """Return the singleton instance, creating it if needed."""
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton — for test isolation."""
        global _instance
        _instance = None

    def register(self, config: McpServerConfig) -> None:
        """Register a use-case MCP server. Overrides bundled by name."""
        self._usecase[config.name] = config
        logger.info("Registered usecase MCP server: %s", config.name)

    def get(self, name: str) -> McpServerConfig:
        """Lookup: usecase first, then bundled. Raises KeyError if not found."""
        if name in self._usecase:
            return self._usecase[name]
        if name in self._bundled:
            return self._bundled[name]
        msg = f"MCP server '{name}' not found. Available: {sorted(self.list_servers())}"
        raise KeyError(msg)

    def list_servers(self) -> list[str]:
        """All registered server names (bundled + usecase, deduplicated)."""
        return sorted({*self._bundled, *self._usecase})
