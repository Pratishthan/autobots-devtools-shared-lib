# ABOUTME: Tests for YAML eval case loader.
# ABOUTME: Validates discovery, parsing, tag filtering, and error handling.

from pathlib import Path

import pytest

from autobots_devtools_shared_lib.eval.core.loader import EvalConfigError, load_eval_cases

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_valid_linear():
    cases = load_eval_cases(str(FIXTURES))
    names = [c.name for c in cases]
    assert "Test linear eval" in names


def test_load_with_tag_filter():
    cases = load_eval_cases(str(FIXTURES), tags=["smoke"])
    assert len(cases) >= 1
    assert all("smoke" in c.tags for c in cases)


def test_load_tag_filter_excludes():
    cases = load_eval_cases(str(FIXTURES), tags=["nonexistent"])
    assert len(cases) == 0


def test_load_invalid_raises():
    """Invalid YAML (linear with no turns) should raise EvalConfigError."""
    invalid_dir = FIXTURES / "invalid_only"
    invalid_dir.mkdir(exist_ok=True)
    invalid_file = invalid_dir / "bad.yaml"
    invalid_file.write_text(
        "eval:\n  name: bad\n  agent: x\n  mode: linear\n  tags: []\n"
        "  state: {}\n  turns: []\n  cost: {}\n"
    )
    try:
        with pytest.raises(EvalConfigError):
            load_eval_cases(str(invalid_dir))
    finally:
        invalid_file.unlink()
        invalid_dir.rmdir()


def test_load_empty_dir_returns_empty(tmp_path):
    """Empty directory returns empty list (no error)."""
    cases = load_eval_cases(str(tmp_path))
    assert cases == []
