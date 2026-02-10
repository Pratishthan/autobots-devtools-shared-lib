# ABOUTME: Integration tests for fserver_client tools against the local file server (ASGI in-process).

import logging
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.filterwarnings(
        "ignore:You should not use the 'timeout' argument with the TestClient"
    ),
]


def _install_fake_logging_config():
    """Install a fake fbp_devtools_agentic_shared_lib.utils.logging_config so fserver_client can be imported."""
    logging_config = types.ModuleType("logging_config")
    logging_config.get_logger = logging.getLogger
    logging_config.setup_logging = lambda: None
    pkg = types.ModuleType("fbp_devtools_agentic_shared_lib")
    pkg.utils = types.ModuleType("utils")
    pkg.utils.logging_config = logging_config
    sys.modules["fbp_devtools_agentic_shared_lib"] = pkg
    sys.modules["fbp_devtools_agentic_shared_lib.utils"] = pkg.utils
    sys.modules["fbp_devtools_agentic_shared_lib.utils.logging_config"] = logging_config


class _TestClientWrapper:
    """Wraps Starlette TestClient so fserver_client's full-URL get/post work in-process."""

    BASE = "http://testserver"

    def __init__(self, test_client):
        self._client = test_client

    def _path(self, url: str) -> str:
        if url.startswith(self.BASE):
            return url[len(self.BASE) :] or "/"
        return url

    def get(self, url: str, **kwargs):
        return self._client.get(self._path(url), **kwargs)

    def post(self, url: str, **kwargs):
        return self._client.post(self._path(url), **kwargs)


@pytest.fixture
def local_file_server(tmp_path):
    """Run the local file server app in-process via TestClient and patch fserver_client to use it."""
    from fastapi.testclient import TestClient

    _install_fake_logging_config()
    # Ensure fserver_client module is loaded so patch path resolves
    # Patch server root so all operations use tmp_path
    import local_file_server.app as app_module

    import autobots_devtools_shared_lib.dynagent.tools.fserver_client  # noqa: F401

    with patch.object(app_module, "FILE_SERVER_ROOT", tmp_path):
        app = app_module.app
        test_client = TestClient(app, base_url="http://testserver")
        wrapper = _TestClientWrapper(test_client)
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value = wrapper
        mock_client_instance.__exit__.return_value = None

        with (
            patch(
                "autobots_devtools_shared_lib.dynagent.tools.fserver_client.FILE_SERVER_BASE_URL",
                "http://testserver",
            ),
            patch(
                "autobots_devtools_shared_lib.dynagent.tools.fserver_client.httpx.Client",
                return_value=mock_client_instance,
            ),
        ):
            yield tmp_path


def test_get_disk_usage(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import get_disk_usage

    result = get_disk_usage.invoke({})
    assert "disk_usage" in result
    assert "size_bytes" in result or "root" in result


def test_list_files_empty(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import list_files

    result = list_files.invoke({"base_path": "", "workspace_context": "{}"})
    assert "[]" in result


def test_write_file_and_list_and_read(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import (
        list_files,
        read_file,
        write_file,
    )

    ws = "{}"
    write_result = write_file.invoke(
        {"file_name": "hello.txt", "content": "Hello world", "workspace_context": ws}
    )
    assert "File written successfully" in write_result
    assert "hello.txt" in write_result

    list_result = list_files.invoke({"base_path": "", "workspace_context": ws})
    assert "hello.txt" in list_result

    read_result = read_file.invoke({"file_name": "hello.txt", "workspace_context": ws})
    assert read_result == "Hello world"


def test_write_file_with_workspace_context(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import (
        list_files,
        read_file,
        write_file,
    )

    ws = '{"agent_name": "test-agent", "repo_name": "test-repo"}'
    write_file.invoke(
        {"file_name": "scoped.txt", "content": "scoped content", "workspace_context": ws}
    )
    list_result = list_files.invoke({"base_path": "", "workspace_context": ws})
    assert "scoped.txt" in list_result
    read_result = read_file.invoke({"file_name": "scoped.txt", "workspace_context": ws})
    assert read_result == "scoped content"


def test_move_file(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import (
        list_files,
        move_file,
        read_file,
        write_file,
    )

    ws = "{}"
    write_file.invoke(
        {"file_name": "move_src.txt", "content": "content to move", "workspace_context": ws}
    )
    move_result = move_file.invoke(
        {
            "source_path": "move_src.txt",
            "destination_path": "subdir/move_dst.txt",
            "workspace_context": ws,
        }
    )
    assert "File moved successfully" in move_result
    read_result = read_file.invoke({"file_name": "subdir/move_dst.txt", "workspace_context": ws})
    assert read_result == "content to move"
    list_result = list_files.invoke({"base_path": "", "workspace_context": ws})
    assert "subdir/move_dst.txt" in list_result
    assert "move_src.txt" not in list_result


def test_create_download_link(local_file_server):
    from autobots_devtools_shared_lib.dynagent.tools.fserver_client import (
        create_download_link,
        write_file,
    )

    ws = "{}"
    write_file.invoke(
        {"file_name": "linkme.txt", "content": "link content", "workspace_context": ws}
    )
    link_result = create_download_link.invoke({"file_name": "linkme.txt", "workspace_context": ws})
    assert "file://" in link_result
    assert "linkme.txt" in link_result or "linkme" in link_result
