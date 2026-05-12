"""Playwright browser wrapper with retries, timeouts, optional image blocking, and robots checks."""
from __future__ import annotations

from dataclasses import dataclass
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import settings
from ..crawler.rate_limit import polite_sleep
from ..crawler.robots import is_allowed
from ..logger import logger


@dataclass
class FetchResult:
    url: str
    html: str
    final_url: str


class BrowserClient:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "BrowserClient":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=settings.headless)
        self._context = self._browser.new_context(
            user_agent=settings.crawler_user_agent,
            viewport={"width": 1366, "height": 768},
        )
        self._context.set_default_timeout(settings.request_timeout_ms)
        if settings.block_images:
            self._context.route("**/*", self._route_filter)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _route_filter(self, route) -> None:
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
        else:
            route.continue_()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        retry=retry_if_exception_type((PlaywrightTimeoutError, RuntimeError)),
        reraise=True,
    )
    def fetch(self, url: str) -> FetchResult | None:
        if not is_allowed(url):
            return None
        polite_sleep()
        logger.info(f"Fetching {url}")
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.request_timeout_ms)
            page.wait_for_load_state("networkidle", timeout=settings.request_timeout_ms)
        except PlaywrightTimeoutError:
            logger.warning(f"Timeout while loading {url}; using current DOM if available")
        html = page.content()
        final_url = page.url
        page.close()
        return FetchResult(url=url, html=html, final_url=final_url)
