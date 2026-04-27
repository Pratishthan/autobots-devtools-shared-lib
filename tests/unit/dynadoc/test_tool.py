# ABOUTME: Unit tests for the make_render_document_tool factory.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynadoc import make_render_document_tool

_BRO_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "bro"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: _BRO_CONFIG,
    )


def test_tool_returns_md_and_errors_dict():
    def load_json(_: str) -> dict:
        return {"who": "you"}

    tool = make_render_document_tool(load_json=load_json)
    result = tool.invoke({"document_name": "smoke_e2e", "strict": True})

    assert isinstance(result, dict)
    assert result["md"].strip() == "hello you"
    assert result["errors"] == []


def test_tool_lenient_returns_errors_list():
    def load_json(_: str) -> dict:
        raise FileNotFoundError("nope")

    tool = make_render_document_tool(load_json=load_json)
    result = tool.invoke({"document_name": "smoke_e2e", "strict": False})

    assert "Section pending" in result["md"]
    assert len(result["errors"]) == 1
    assert result["errors"][0]["kind"] == "missing_json"
    assert result["errors"][0]["node_path"] == "smoke_e2e"
