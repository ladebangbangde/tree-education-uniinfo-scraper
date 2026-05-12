"""Application configuration loaded from environment variables."""
from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://tree_user:tree_password@localhost:3306/tree_education_uniinfo",
    )
    headless: bool = _bool("HEADLESS", True)
    block_images: bool = _bool("BLOCK_IMAGES", True)
    request_min_delay: float = float(os.getenv("REQUEST_MIN_DELAY", "1"))
    request_max_delay: float = float(os.getenv("REQUEST_MAX_DELAY", "3"))
    crawler_user_agent: str = os.getenv(
        "CRAWLER_USER_AGENT", "Mozilla/5.0 TreeEducationBot/0.1"
    )
    snapshot_dir: str = os.getenv("SNAPSHOT_DIR", "data/snapshots")
    request_timeout_ms: int = int(os.getenv("REQUEST_TIMEOUT_MS", "30000"))
    source_site: str = "bachelorsportal"


settings = Settings()
