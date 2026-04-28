# ABOUTME: Tests for workspace file staging and teardown.
# ABOUTME: Validates file server staging via provider, missing src detection, and no-op teardown.
from pathlib import Path
from unittest.mock import patch

import pytest

from autobots_devtools_shared_lib.eval.core.workspace import (
    register_workspace_context_provider,
    resolve_workspace_context,
    setup_workspace,
    teardown_workspace,
)
from autobots_devtools_shared_lib.eval.models.eval_case import SetupConfig, WorkspaceFile


class _StubProvider:
    def get_workspace_context(self, state: dict) -> str:
        return '{"workspace_base_path": "test-user/test-repo-MER-99999"}'


@pytest.fixture(autouse=True)
def _register_stub_provider():
    register_workspace_context_provider(_StubProvider())


@pytest.fixture()
def fixture_dir(tmp_path) -> Path:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "input.md").write_text("# Test LLD\nModel: Party")
    (fixtures / "meta.json").write_text('{"models": []}')
    return fixtures


class TestSetupWorkspace:
    def test_stages_single_file(self, fixture_dir):
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(
                    src=str(fixture_dir / "input.md"),
                    dest="docs/FeatureLLD/MER-99999/party.md",
                )
            ]
        )
        with patch(
            "autobots_devtools_shared_lib.eval.core.workspace.write_file",
            return_value="File written successfully",
        ) as mock_write:
            setup_workspace(config)
            mock_write.assert_called_once()
            call_args = mock_write.call_args
            assert call_args[0][0] == "docs/FeatureLLD/MER-99999/party.md"
            assert "Party" in call_args[0][1]
            assert "test-user/test-repo-MER-99999" in call_args[0][2]

    def test_stages_multiple_files(self, fixture_dir):
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(src=str(fixture_dir / "input.md"), dest="docs/LLD.md"),
                WorkspaceFile(src=str(fixture_dir / "meta.json"), dest="meta/models.json"),
            ]
        )
        with patch(
            "autobots_devtools_shared_lib.eval.core.workspace.write_file",
            return_value="File written successfully",
        ) as mock_write:
            setup_workspace(config)
            assert mock_write.call_count == 2
            dest_args = [c[0][0] for c in mock_write.call_args_list]
            assert "docs/LLD.md" in dest_args
            assert "meta/models.json" in dest_args

    def test_empty_setup(self):
        config = SetupConfig()
        with patch("autobots_devtools_shared_lib.eval.core.workspace.write_file") as mock_write:
            setup_workspace(config)
            mock_write.assert_not_called()

    def test_missing_src_raises(self):
        config = SetupConfig(
            workspace_files=[WorkspaceFile(src="/nonexistent/file.md", dest="docs/LLD.md")]
        )
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            setup_workspace(config)

    def test_file_server_error_raises(self, fixture_dir):
        config = SetupConfig(
            workspace_files=[WorkspaceFile(src=str(fixture_dir / "input.md"), dest="docs/LLD.md")]
        )
        with (
            patch(
                "autobots_devtools_shared_lib.eval.core.workspace.write_file",
                return_value="Error: connection refused",
            ),
            pytest.raises(RuntimeError, match="File server failed"),
        ):
            setup_workspace(config)

    def test_state_passed_to_provider(self):
        state = {"user_name": "alice", "repo_name": "myrepo", "jira_number": "MER-1"}
        ctx = resolve_workspace_context(state)
        assert "workspace_base_path" in ctx


class TestTeardownWorkspace:
    def test_noop(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("test")
        teardown_workspace(str(workspace))
        # Directory is NOT removed — teardown is a no-op (file server manages storage)
        assert workspace.exists()

    def test_noop_if_missing(self, tmp_path):
        workspace = tmp_path / "workspace"
        teardown_workspace(str(workspace))  # Should not raise
