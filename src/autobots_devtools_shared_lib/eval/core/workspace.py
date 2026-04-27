# ABOUTME: Workspace staging for eval runs + WorkspaceContextProvider interface.
# ABOUTME: Consumers register a provider so shared-lib never hard-codes workspace path formation.
"""Workspace file staging and pluggable workspace context provider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from autobots_devtools_shared_lib.common.utils.fserver_client_utils import write_file
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

if TYPE_CHECKING:
    from langchain.agents import AgentState

    from autobots_devtools_shared_lib.eval.models.eval_case import SetupConfig

_state_schema: type[Any] = Dynagent


def register_eval_state_schema(schema: type[Any]) -> None:
    """Register the LangGraph state schema for eval agent invocations.

    Call once in conftest.py when your agents use a custom state class (e.g. MerState)
    that extends Dynagent with domain-specific fields. Without this, ainvoke_agent
    defaults to Dynagent and drops extra state fields (e.g. jira_number, repo_name).

    Example (MER consumer)::

        from autobots_devtools_shared_lib.eval.core.workspace import register_eval_state_schema
        from autobots_agents_mer.common.models.state import MerState

        register_eval_state_schema(MerState)
    """
    global _state_schema
    _state_schema = schema


def resolve_eval_state_schema() -> type[AgentState]:
    """Return the registered state schema for eval agent invocations."""
    return _state_schema


class WorkspaceContextProvider(Protocol):
    """Protocol for building file-server workspace context from agent state.

    Implement this in your consumer conftest.py and register via
    register_workspace_context_provider(). Path formation is intentionally
    kept out of shared-lib — each consumer app may have a different convention.

    Example (MER consumer)::

        class MerWorkspaceContextProvider:
            def get_workspace_context(self, state: dict) -> str:
                ws = get_workspace_context(state)  # MER util
                return json.dumps(ws)

        register_workspace_context_provider(MerWorkspaceContextProvider())
    """

    def get_workspace_context(self, state: dict[str, Any]) -> str:
        """Return workspace_context JSON string for fserver_client_utils calls.

        Args:
            state: Agent state dict (e.g. user_name, repo_name, jira_number).

        Returns:
            JSON string, e.g. '{"workspace_base_path": "alice/fbp-core-MER-99999"}'.
        """
        ...


_provider: WorkspaceContextProvider | None = None


def register_workspace_context_provider(provider: WorkspaceContextProvider) -> None:
    """Register the workspace context provider.

    Call once at eval startup, typically from conftest.py, before any evals run.
    """
    global _provider
    _provider = provider


def resolve_workspace_context(state: dict[str, Any]) -> str:
    """Return workspace_context JSON via the registered provider.

    Raises:
        RuntimeError: If no provider has been registered.
    """
    if _provider is None:
        raise RuntimeError(
            "No WorkspaceContextProvider registered. "
            "Call register_workspace_context_provider() in your conftest.py before running evals."
        )
    return _provider.get_workspace_context(state)


def setup_workspace(config: SetupConfig, state: dict[str, Any] | None = None) -> None:
    """Stage fixture files into the file server workspace before agent invocation.

    Args:
        config: Setup configuration with workspace_files to stage.
        state: EvalCase state dict used to resolve workspace context via the provider.

    Raises:
        FileNotFoundError: If a source fixture file does not exist.
        RuntimeError: If the file server returns an error or no provider is registered.
    """
    app_root_path = os.getenv("APP_ROOT_PATH", "")
    workspace_context = resolve_workspace_context(state or {})

    for wf in config.workspace_files:
        src = Path(app_root_path, wf.src)
        if not src.exists():
            raise FileNotFoundError(
                f"Fixture file not found: {src}. "
                f"Ensure the file exists in the eval fixtures directory."
            )
        content = src.read_text(encoding="utf-8")
        result = write_file(wf.dest, content, workspace_context)
        if result.startswith("Error"):
            raise RuntimeError(f"File server failed to stage '{wf.src}' → '{wf.dest}': {result}")


def teardown_workspace(_workspace_path: str) -> None:
    """No-op: file server manages its own storage. Kept for interface compatibility."""
    pass
