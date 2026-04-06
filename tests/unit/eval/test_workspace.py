# ABOUTME: Tests for workspace file staging and teardown.
# ABOUTME: Validates file copying, directory creation, and cleanup.
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from autobots_devtools_shared_lib.eval.core.workspace import (
    setup_workspace,
    teardown_workspace,
)
from autobots_devtools_shared_lib.eval.models.eval_case import SetupConfig, WorkspaceFile


@pytest.fixture()
def fixture_dir(tmp_path) -> Path:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "input.md").write_text("# Test LLD\nModel: Party")
    (fixtures / "meta.json").write_text('{"models": []}')
    return fixtures


class TestSetupWorkspaceWithFileServer:
    def test_calls_move_file_for_each_workspace_file(self, tmp_path):
        state = {"user_name": "alice", "repo_name": "my-repo", "jira_number": "MER-42"}
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(src="/fixtures/input.md", dest="docs/LLD.md"),
                WorkspaceFile(src="/fixtures/meta.json", dest="meta/models.json"),
            ]
        )
        with patch("autobots_devtools_shared_lib.eval.core.workspace.move_file") as mock_move:
            mock_move.return_value = "File moved successfully"
            setup_workspace(config, str(tmp_path / "workspace"), state=state)

        assert mock_move.call_count == 2
        mock_move.assert_any_call(
            "/fixtures/input.md",
            str(tmp_path / "workspace" / "docs/LLD.md"),
            json.dumps(state),
        )
        mock_move.assert_any_call(
            "/fixtures/meta.json",
            str(tmp_path / "workspace" / "meta/models.json"),
            json.dumps(state),
        )

    def test_empty_state_passes_empty_json(self, tmp_path):
        config = SetupConfig(workspace_files=[WorkspaceFile(src="/fixtures/f.md", dest="f.md")])
        with patch("autobots_devtools_shared_lib.eval.core.workspace.move_file") as mock_move:
            mock_move.return_value = "File moved successfully"
            setup_workspace(config, str(tmp_path / "ws"))

        mock_move.assert_called_once_with(
            "/fixtures/f.md",
            str(tmp_path / "ws" / "f.md"),
            "{}",
        )

    def test_no_files_no_move_called(self, tmp_path):
        config = SetupConfig()
        with patch("autobots_devtools_shared_lib.eval.core.workspace.move_file") as mock_move:
            setup_workspace(config, str(tmp_path / "ws"))
        mock_move.assert_not_called()

    def test_raises_on_file_server_error(self, tmp_path):
        config = SetupConfig(workspace_files=[WorkspaceFile(src="/fixtures/f.md", dest="f.md")])
        with patch("autobots_devtools_shared_lib.eval.core.workspace.move_file") as mock_move:
            mock_move.return_value = "Error moving file: HTTP 404 - Not Found"
            with pytest.raises(RuntimeError, match="File server failed to stage"):
                setup_workspace(config, str(tmp_path / "ws"))


class TestSetupWorkspace:
    def test_creates_workspace_dir(self, tmp_path):
        workspace = tmp_path / "workspace"
        config = SetupConfig(
            workspace_files=[WorkspaceFile(src="/fixtures/input.md", dest="docs/LLD.md")]
        )
        with patch(
            "autobots_devtools_shared_lib.eval.core.workspace.move_file",
            return_value="File moved successfully",
        ):
            setup_workspace(config, str(workspace))
        assert workspace.exists()

    def test_calls_move_for_multiple_files(self, tmp_path):
        workspace = tmp_path / "workspace"
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(src="/fixtures/input.md", dest="docs/LLD.md"),
                WorkspaceFile(src="/fixtures/meta.json", dest="meta/models.json"),
            ]
        )
        with patch(
            "autobots_devtools_shared_lib.eval.core.workspace.move_file",
            return_value="File moved successfully",
        ) as mock_move:
            setup_workspace(config, str(workspace))
        assert mock_move.call_count == 2

    def test_empty_setup(self, tmp_path):
        workspace = tmp_path / "workspace"
        config = SetupConfig()
        with patch("autobots_devtools_shared_lib.eval.core.workspace.move_file"):
            setup_workspace(config, str(workspace))
        assert workspace.exists()


class TestTeardownWorkspace:
    def test_removes_workspace(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("test")
        teardown_workspace(str(workspace))
        assert not workspace.exists()

    def test_noop_if_missing(self, tmp_path):
        workspace = tmp_path / "workspace"
        teardown_workspace(str(workspace))  # Should not raise
