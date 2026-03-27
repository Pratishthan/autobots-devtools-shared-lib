# ABOUTME: Tests for workspace file staging and teardown.
# ABOUTME: Validates file copying, directory creation, and cleanup.
from pathlib import Path

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


class TestSetupWorkspace:
    def test_creates_workspace_dir(self, tmp_path, fixture_dir):
        workspace = tmp_path / "workspace"
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(
                    src=str(fixture_dir / "input.md"),
                    dest="docs/FeatureLLD/MER-99999---Party.md",
                )
            ]
        )
        setup_workspace(config, str(workspace))
        assert workspace.exists()
        assert (workspace / "docs/FeatureLLD/MER-99999---Party.md").exists()
        content = (workspace / "docs/FeatureLLD/MER-99999---Party.md").read_text()
        assert "Party" in content

    def test_stages_multiple_files(self, tmp_path, fixture_dir):
        workspace = tmp_path / "workspace"
        config = SetupConfig(
            workspace_files=[
                WorkspaceFile(
                    src=str(fixture_dir / "input.md"),
                    dest="docs/LLD.md",
                ),
                WorkspaceFile(
                    src=str(fixture_dir / "meta.json"),
                    dest="meta/models.json",
                ),
            ]
        )
        setup_workspace(config, str(workspace))
        assert (workspace / "docs/LLD.md").exists()
        assert (workspace / "meta/models.json").exists()

    def test_empty_setup(self, tmp_path):
        workspace = tmp_path / "workspace"
        config = SetupConfig()
        setup_workspace(config, str(workspace))
        assert workspace.exists()

    def test_missing_src_raises(self, tmp_path):
        workspace = tmp_path / "workspace"
        config = SetupConfig(
            workspace_files=[WorkspaceFile(src="/nonexistent/file.md", dest="docs/LLD.md")]
        )
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            setup_workspace(config, str(workspace))


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
