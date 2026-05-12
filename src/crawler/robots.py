"""robots.txt compliance checks."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import requests
from ..config import settings
from ..logger import logger


@lru_cache(maxsize=64)
def _parser_for_base(base_url: str) -> RobotFileParser:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = requests.get(robots_url, timeout=10, headers={"User-Agent": settings.crawler_user_agent})
        if response.status_code >= 400:
            logger.warning(f"robots.txt unavailable ({response.status_code}) at {robots_url}; defaulting to disallow for safety")
            parser.parse(["User-agent: *", "Disallow: /"])
        else:
            parser.parse(response.text.splitlines())
    except requests.RequestException as exc:
        logger.warning(f"Could not fetch robots.txt {robots_url}: {exc}; defaulting to disallow for safety")
        parser.parse(["User-agent: *", "Disallow: /"])
    return parser


def is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    base = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    allowed = _parser_for_base(base).can_fetch(settings.crawler_user_agent, url)
    if not allowed:
        logger.warning(f"robots.txt disallows URL, skipping: {url}")
    return allowed
