"""API settings read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime configuration; built from the environment by ``from_env``."""

    database_url: str
    output_dir: Path = Path("output")
    upload_dir: Path = Path("uploads")
    max_upload_mb: int = 500
    max_concurrent_jobs: int = 1
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])

    @classmethod
    def from_env(cls) -> Settings:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set (see .env.example)")
        return cls(
            database_url=url,
            output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
            upload_dir=Path(os.getenv("UPLOAD_DIR", "uploads")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "500")),
            max_concurrent_jobs=int(os.getenv("MAX_CONCURRENT_JOBS", "1")),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        )
