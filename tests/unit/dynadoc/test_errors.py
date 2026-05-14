# ABOUTME: Unit tests for dynadoc error/result dataclasses.
# ABOUTME: Validates RenderError/RenderResult shapes and exception subclasses.

import pytest

from autobots_devtools_shared_lib.dynadoc.errors import (
    MalformedJsonError,
    ManifestValidationError,
    MissingInputError,
    MissingTemplateError,
    RenderError,
    RenderResult,
    UndefinedVariableError,
)


def test_render_error_kinds():
    err = RenderError(
        node_path="lld.data.models",
        kind="missing_json",
        message="x",
    )
    assert err.cause is None
    assert err.kind == "missing_json"


def test_render_result_defaults_errors_to_empty_list():
    r = RenderResult(md="# hi")
    assert r.errors == []


def test_render_result_holds_errors():
    e = RenderError(node_path="a", kind="missing_template", message="m")
    r = RenderResult(md="x", errors=[e])
    assert r.errors[0].node_path == "a"


@pytest.mark.parametrize(
    "exc",
    [
        MissingInputError,
        MissingTemplateError,
        UndefinedVariableError,
        MalformedJsonError,
        ManifestValidationError,
    ],
)
def test_dynadoc_exceptions_are_exceptions(exc):
    with pytest.raises(exc):
        raise exc("boom")
