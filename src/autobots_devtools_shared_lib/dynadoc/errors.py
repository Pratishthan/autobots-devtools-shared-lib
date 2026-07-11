# ABOUTME: Error types and result dataclasses for the dynadoc renderer.
# ABOUTME: RenderError describes per-node failures; exceptions are raised in strict mode.

from dataclasses import dataclass, field
from typing import Literal

ErrorKind = Literal["missing_json", "missing_template", "undefined_variable"]


@dataclass
class RenderError:
    node_path: str
    kind: ErrorKind
    message: str
    cause: Exception | None = None


@dataclass
class RenderResult:
    md: str
    errors: list[RenderError] = field(default_factory=list)


class DynadocError(Exception):
    """Base class for dynadoc errors."""


class MissingInputError(DynadocError):
    """Raised in strict mode when a leaf's JSON file is not found."""


class MissingTemplateError(DynadocError):
    """Raised in strict mode when a template file is not found."""


class UndefinedVariableError(DynadocError):
    """Raised in strict mode when a Jinja template references an undefined variable."""


class MalformedJsonError(DynadocError):
    """Raised in any mode when a JSON input fails to parse."""


class ManifestValidationError(DynadocError):
    """Raised when the dynadoc.yaml manifest is structurally invalid."""
