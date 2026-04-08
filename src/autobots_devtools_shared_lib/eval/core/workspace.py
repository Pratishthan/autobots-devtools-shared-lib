# ABOUTME: Workspace file staging for eval runs.
# ABOUTME: Copies fixture files into workspace directory before agent invocation.
"""Workspace file staging for eval runs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.eval_case import SetupConfig


def setup_workspace(config: SetupConfig, workspace_path: str) -> None:
    """Create workspace directory and stage fixture files.

    Args:
        config: Setup configuration with workspace_files to stage.
        workspace_path: Target workspace directory path.

    Raises:
        FileNotFoundError: If a source fixture file does not exist.
    """
    import os

    app_root_path = os.getenv("APP_ROOT_PATH", "")
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    for wf in config.workspace_files:
        src = Path(app_root_path, wf.src)
        if not src.exists():
            raise FileNotFoundError(
                f"Fixture file not found: {src}. "
                f"Ensure the file exists in the eval fixtures directory."
            )
        dest = workspace / wf.dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def teardown_workspace(workspace_path: str) -> None:
    """Remove workspace directory and all contents.

    Args:
        workspace_path: Workspace directory to remove.
    """
    workspace = Path(workspace_path)
    if workspace.exists():
        shutil.rmtree(workspace)
