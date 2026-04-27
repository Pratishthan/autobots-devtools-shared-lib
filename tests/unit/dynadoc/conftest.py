# ABOUTME: Shared in-memory loader fixtures for dynadoc engine tests.

from collections.abc import Callable


def make_json_loader(data: dict[str, dict]) -> Callable[[str], dict]:
    """Return a load_json that serves from an in-memory dict; raises FileNotFoundError otherwise."""

    def _loader(path: str) -> dict:
        if path not in data:
            raise FileNotFoundError(path)
        return data[path]

    return _loader


def make_template_loader(templates: dict[str, str]) -> Callable[[str], str]:
    def _loader(name: str) -> str:
        if name not in templates:
            raise FileNotFoundError(name)
        return templates[name]

    return _loader
