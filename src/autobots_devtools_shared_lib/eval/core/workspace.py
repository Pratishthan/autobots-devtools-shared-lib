# ABOUTME: Workspace file staging for eval runs.
# ABOUTME: Uses file server to move fixture files into workspace before agent invocation.
"""Workspace file staging for eval runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.common.utils.fserver_client_utils import move_file

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.eval_case import SetupConfig


def setup_workspace(
    config: SetupConfig,
    workspace_path: str,
    state: dict[str, Any] | None = None,
) -> None:
    """Create workspace directory and stage fixture files via file server.

    Args:
        config: Setup configuration with workspace_files to stage.
        workspace_path: Target workspace directory path.
        state: EvalCase state dict containing workspace context (user_name,
               repo_name, jira_number, etc.) passed to the file server.
    """
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    workspace_context = json.dumps(state) if state else "{}"

    for wf in config.workspace_files:
        dest = workspace / wf.dest
        result = move_file(wf.src, str(dest), workspace_context)
        if result.startswith("Error"):
            raise RuntimeError(f"File server failed to stage '{wf.src}' → '{dest}': {result}")


def teardown_workspace(workspace_path: str) -> None:
    """Remove workspace directory and all contents.

    Args:
        workspace_path: Workspace directory to remove.
    """
    workspace = Path(workspace_path)
    if workspace.exists():
        shutil.rmtree(workspace)
