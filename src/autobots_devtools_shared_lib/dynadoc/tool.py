# ABOUTME: Factory that builds a LangChain tool wrapping render_document.
# ABOUTME: Domains call make_render_document_tool(load_json=...) and register the result.

from collections.abc import Callable
from dataclasses import asdict

from langchain.tools import tool

from autobots_devtools_shared_lib.dynadoc.engine import render_document


def make_render_document_tool(load_json: Callable[[str], dict]):
    """Build a Dynagent-compatible tool that renders a named document.

    The caller supplies `load_json` (workspace-aware) once at registration time.
    The tool returns a dict {md: str, errors: list[dict]} so it serializes cleanly
    through the agent message bus.
    """

    @tool
    def render_document_tool(document_name: str, strict: bool = True) -> dict:
        """Render a named dynadoc document to Markdown.

        Args:
            document_name: Top-level key in dynadoc.yaml (e.g. "lld").
            strict: When True, raise on missing inputs/templates. When False,
                emit "Section pending" placeholders and return errors in the result.
        """
        result = render_document(document_name, load_json=load_json, strict=strict)
        return {
            "md": result.md,
            "errors": [{k: v for k, v in asdict(e).items() if k != "cause"} for e in result.errors],
        }

    return render_document_tool
