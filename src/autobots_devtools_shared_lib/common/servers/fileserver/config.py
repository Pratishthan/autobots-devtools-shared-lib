"""Configuration for the file server."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _parse_cors_origins(value: str) -> list[str]:
    """Parse comma-separated CORS origins."""
    if not value or not value.strip():
        return ["*"]
    return [o.strip() for o in value.split(",") if o.strip()]


class FileServerConfig:
    """Root directory to serve and related settings. Production-ready options for open source."""

    root: Path = Path(os.getenv("FILE_SERVER_ROOT", ".")).resolve()
    host: str = os.getenv("FILE_SERVER_HOST", "0.0.0.0")  # noqa: S104
    port: int = int(os.getenv("FILE_SERVER_PORT", "9002"))
    # Max upload size in MB (0 = no limit; apply in write_file if needed)
    max_file_size_mb: int = int(os.getenv("FILE_SERVER_MAX_FILE_SIZE_MB", "0"))
    # CORS: set FILE_SERVER_ENABLE_CORS=1 and optionally FILE_SERVER_CORS_ORIGINS=*
    enable_cors: bool = os.getenv("FILE_SERVER_ENABLE_CORS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    cors_origins: list[str] = _parse_cors_origins(os.getenv("FILE_SERVER_CORS_ORIGINS", "*"))
    # OpenTelemetry (Langfuse): enable when both Langfuse keys are set
    langfuse_enabled: bool = os.getenv("LANGFUSE_ENABLED", "").strip().lower() == "true"

    @classmethod
    def ensure_root(cls) -> None:
        """Ensure root directory exists (create if missing)."""
        cls.root.mkdir(parents=True, exist_ok=True)
