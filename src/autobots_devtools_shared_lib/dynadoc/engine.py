# ABOUTME: dynadoc render engine — recursive node tree → Markdown string.
# ABOUTME: Pure core; caller supplies load_json (workspace I/O).

from collections.abc import Callable

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynadoc.errors import (
    MalformedJsonError,
    MissingInputError,
    MissingTemplateError,
    RenderError,
    RenderResult,
    UndefinedVariableError,
)
from autobots_devtools_shared_lib.dynadoc.manifest import Node, find_document, parse_manifest

logger = get_logger(__name__)

JsonLoader = Callable[[str], dict]
TemplateLoader = Callable[[str], str]


def _placeholder(node_path: str) -> str:
    return f"> _Section pending: {node_path}_"


def _make_env() -> Environment:
    # Output is Markdown, not HTML — HTML autoescape would corrupt MD (e.g. mangle &, <, >).
    return Environment(
        undefined=StrictUndefined,
        autoescape=False,  # noqa: S701
        keep_trailing_newline=False,
    )


def render_tree(
    node: Node,
    load_json: JsonLoader,
    load_template: TemplateLoader,
    strict: bool,
) -> RenderResult:
    """Render a Node subtree to MD.

    This is the engine's internal entry point. Public callers use render_document() in tool/__init__.
    """
    errors: list[RenderError] = []
    env = _make_env()
    md = _render_node(node, load_json, load_template, env, strict, errors)
    return RenderResult(md=md, errors=errors)


def _render_node(
    node: Node,
    load_json: JsonLoader,
    load_template: TemplateLoader,
    env: Environment,
    strict: bool,
    errors: list[RenderError],
) -> str:
    if node.is_leaf():
        return _render_leaf(node, load_json, load_template, env, strict, errors)
    return _render_composite(node, load_json, load_template, env, strict, errors)


def _render_leaf(
    node: Node,
    load_json: JsonLoader,
    load_template: TemplateLoader,
    env: Environment,
    strict: bool,
    errors: list[RenderError],
) -> str:
    assert node.json_path is not None

    # 1. load JSON
    try:
        data = load_json(node.json_path)
    except FileNotFoundError as e:
        if strict:
            raise MissingInputError(
                f"JSON not found at '{node.json_path}' for node '{node.path}'"
            ) from e
        errors.append(
            RenderError(
                node_path=node.path,
                kind="missing_json",
                message=f"JSON not found: {node.json_path}",
                cause=e,
            )
        )
        return _placeholder(node.path)
    except Exception as e:
        # Anything else from the loader is treated as malformed input — not recoverable.
        raise MalformedJsonError(
            f"Failed to load JSON for node '{node.path}' from '{node.json_path}': {e}"
        ) from e

    # 2. load + render template
    return _render_with_template(node, node.template, data, load_template, env, strict, errors)


def _render_composite(
    node: Node,
    load_json: JsonLoader,
    load_template: TemplateLoader,
    env: Environment,
    strict: bool,
    errors: list[RenderError],
) -> str:
    sections: dict[str, str] = {}
    for name, child in node.children.items():  # insertion order
        sections[name] = _render_node(child, load_json, load_template, env, strict, errors)
    return _render_with_template(
        node, node.template, {"sections": sections}, load_template, env, strict, errors
    )


def _render_with_template(
    node: Node,
    template_name: str,
    context: dict,
    load_template: TemplateLoader,
    env: Environment,
    strict: bool,
    errors: list[RenderError],
) -> str:
    try:
        source = load_template(template_name)
    except FileNotFoundError as e:
        if strict:
            raise MissingTemplateError(
                f"Template not found: '{template_name}' for node '{node.path}'"
            ) from e
        errors.append(
            RenderError(
                node_path=node.path,
                kind="missing_template",
                message=f"Template not found: {template_name}",
                cause=e,
            )
        )
        return _placeholder(node.path)

    try:
        tmpl = env.from_string(source)
        return tmpl.render(**context)
    except UndefinedError as e:
        if strict:
            raise UndefinedVariableError(
                f"Undefined variable in template '{template_name}' for node '{node.path}': {e}"
            ) from e
        errors.append(
            RenderError(
                node_path=node.path,
                kind="undefined_variable",
                message=str(e),
                cause=e,
            )
        )
        return _placeholder(node.path)
    except TemplateSyntaxError as e:
        # Syntax errors are author bugs — surface in both modes as a generic DynadocError.
        from autobots_devtools_shared_lib.dynadoc.errors import DynadocError

        raise DynadocError(
            f"Template syntax error in '{template_name}' for node '{node.path}': {e}"
        ) from e


def render_document(
    document_name: str,
    load_json: JsonLoader,
    strict: bool = True,
) -> RenderResult:
    """Top-level entry point.

    Looks up the document in the active domain's dynadoc.yaml and renders it.
    Templates and the manifest are resolved from DYNAGENT_CONFIG_ROOT_DIR.
    """
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
        load_render_manifest,
        load_template,
    )

    raw = load_render_manifest()
    documents = parse_manifest(raw)
    node = find_document(documents, document_name)
    return render_tree(node, load_json, load_template, strict=strict)
