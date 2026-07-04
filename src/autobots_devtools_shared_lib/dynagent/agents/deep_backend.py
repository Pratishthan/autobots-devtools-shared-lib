# ABOUTME: Backend registry for the deep engine's virtual filesystem.
# ABOUTME: Resolves deep-agents.yaml default_backend config into deepagents backends.

from collections.abc import Callable
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend

from autobots_devtools_shared_lib.common.observability import get_logger

logger = get_logger(__name__)


def _build_state(_cfg: dict[str, Any], **_kw: Any) -> None:
    """deepagents defaults to StateBackend when backend is None."""


def _build_filesystem(cfg: dict[str, Any], **_kw: Any) -> FilesystemBackend:
    root_dir = cfg.get("root_dir")
    if root_dir:
        Path(root_dir).mkdir(parents=True, exist_ok=True)
    return FilesystemBackend(root_dir=root_dir, virtual_mode=True)


_BACKEND_REGISTRY: dict[str, Callable[..., Any]] = {
    "state": _build_state,
    "filesystem": _build_filesystem,
}


def _build_backend(cfg: dict[str, Any], *, store: Any = None) -> Any:
    backend_type = cfg.get("type", "state")
    builder = _BACKEND_REGISTRY.get(backend_type)
    if builder is None:
        msg = f"Unknown backend type '{backend_type}'. Valid types: {sorted(_BACKEND_REGISTRY)}"
        raise ValueError(msg)
    return builder(cfg, store=store)


def resolve_backend(
    backend_config: dict[str, Any] | None,
    override: Any = None,
    store: Any = None,
) -> Any:
    """Resolve the domain backend; an explicit backend= kwarg wins over YAML."""
    if override is not None:
        return override
    if not backend_config:
        return None
    backend = _build_backend(backend_config, store=store)
    logger.info(f"resolve_backend: type={backend_config.get('type', 'state')}")
    return backend
