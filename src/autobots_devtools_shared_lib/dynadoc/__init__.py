# ABOUTME: dynadoc public API — deterministic JSON → Markdown renderer.

from autobots_devtools_shared_lib.dynadoc.engine import render_document, render_tree
from autobots_devtools_shared_lib.dynadoc.errors import (
    DynadocError,
    MalformedJsonError,
    ManifestValidationError,
    MissingInputError,
    MissingTemplateError,
    RenderError,
    RenderResult,
    UndefinedVariableError,
)
from autobots_devtools_shared_lib.dynadoc.tool import make_render_document_tool

__all__ = [
    "DynadocError",
    "MalformedJsonError",
    "ManifestValidationError",
    "MissingInputError",
    "MissingTemplateError",
    "RenderError",
    "RenderResult",
    "UndefinedVariableError",
    "make_render_document_tool",
    "render_document",
    "render_tree",
]
