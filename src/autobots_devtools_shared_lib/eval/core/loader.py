# ABOUTME: YAML eval case discovery and parsing.
# ABOUTME: Recursively finds *.yaml files, validates with Pydantic, returns EvalCase list.

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from autobots_devtools_shared_lib.eval.models.eval_case import EvalCase

logger = logging.getLogger(__name__)


class EvalConfigError(Exception):
    """Raised when an eval YAML file is invalid."""


def load_eval_cases(
    eval_dir: str,
    tags: list[str] | None = None,
) -> list[EvalCase]:
    """Discover and parse YAML eval cases from a directory.

    Args:
        eval_dir: Root directory to search for *.yaml files.
        tags: If provided, only return cases that have at least one matching tag.

    Returns:
        List of validated EvalCase objects.

    Raises:
        EvalConfigError: If a YAML file is malformed or fails validation.
    """
    root = Path(eval_dir)
    if not root.is_dir():
        logger.warning("Eval directory does not exist: %s", eval_dir)
        return []

    cases: list[EvalCase] = []

    for yaml_path in sorted(root.rglob("*.yaml")):
        try:
            raw = yaml.safe_load(yaml_path.read_text())
            if raw is None or "eval" not in raw:
                continue  # skip non-eval YAML files

            case = EvalCase.model_validate(raw["eval"])

            if tags and not set(tags) & set(case.tags):
                continue

            cases.append(case)
        except (ValidationError, KeyError, yaml.YAMLError) as e:
            raise EvalConfigError(f"Invalid eval case at {yaml_path}: {e}") from e

    return cases
