"""Application configuration loaded from environment variables."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "tree_education_uniinfo")
    user = os.getenv("DB_USER", "tree_user")
    password = os.getenv("DB_PASSWORD", "tree_password")

    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}"
    )


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=_database_url)
    headless: bool = _bool("HEADLESS", True)
    block_images: bool = _bool("BLOCK_IMAGES", True)
    request_min_delay: float = float(os.getenv("REQUEST_MIN_DELAY", "1"))
    request_max_delay: float = float(os.getenv("REQUEST_MAX_DELAY", "3"))
    crawler_user_agent: str = os.getenv(
        "CRAWLER_USER_AGENT", "Mozilla/5.0 TreeEducationBot/0.1"
    )
    snapshot_dir: str = os.getenv("SNAPSHOT_DIR", "data/snapshots")
    request_timeout_ms: int = int(os.getenv("REQUEST_TIMEOUT_MS", "90000"))
    source_site: str = "bachelorsportal"


settings = Settings()
