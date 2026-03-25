"""Unit tests for file server git endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from autobots_devtools_shared_lib.common.servers.fileserver.app import app

client = TestClient(app)


class TestGitStatusEndpoint:
    @patch("autobots_devtools_shared_lib.common.servers.fileserver.app.subprocess")
    def test_returns_status_and_diff_stat(self, mock_subprocess):
        mock_subprocess.run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.py\n?? new.txt\n", stderr=""),
            MagicMock(returncode=0, stdout=" 1 file changed, 10 insertions(+)\n", stderr=""),
        ]
        resp = client.post("/gitStatus", json={"workspace_context": {}, "session_id": "s1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "porcelain" in data
        assert "diff_stat" in data


class TestGitDiffEndpoint:
    @patch("autobots_devtools_shared_lib.common.servers.fileserver.app.subprocess")
    def test_returns_unified_diff(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/file.py b/file.py\n+added line\n", stderr=""
        )
        resp = client.post(
            "/gitDiff",
            json={
                "workspace_context": {},
                "file_path": "file.py",
                "session_id": "s1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "diff" in data

    def test_rejects_empty_file_path(self):
        resp = client.post(
            "/gitDiff",
            json={
                "workspace_context": {},
                "file_path": "",
            },
        )
        assert resp.status_code == 422  # validation error
