"""File server package (config, models, FastAPI app)."""

from .app import app  # re-export for convenience

__all__ = ["app"]
