"""Playwright browser wrapper with retries, timeouts, optional image blocking, and robots checks."""
from __future__ import annotations

from dataclasses import dataclass
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, sync_playwright
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from ..config import settings
from ..crawler.rate_limit import polite_sleep
from ..crawler.robots import is_allowed
from ..logger import logger


def _log_retry(retry_state) -> None:
    """Log tenacity retry events with loguru formatting."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retrying fetch after attempt {} in {:.2f}s because of: {}",
        retry_state.attempt_number,
        retry_state.next_action.sleep if retry_state.next_action else 0,
        exc,
    )


@dataclass
class FetchResult:
    """Successful page fetch result."""

    url: str
    html: str
    final_url: str


class BrowserClient:
    """Small synchronous Playwright client for low-volume compliant crawling."""

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
        logger.info(
            "Browser started: headless={}, block_images={}, timeout_ms={}",
            settings.headless,
            settings.block_images,
            settings.request_timeout_ms,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Browser stopped")

    def _route_filter(self, route) -> None:
        """Optionally skip heavy resources while allowing HTML/JS/XHR."""
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
        else:
            route.continue_()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        retry=retry_if_exception_type((PlaywrightTimeoutError, PlaywrightError, RuntimeError)),
        before_sleep=_log_retry,
        reraise=True,
    )
    def fetch(self, url: str) -> FetchResult | None:
        """Fetch a public URL after robots and rate-limit checks.

        Returns `None` only when robots.txt disallows the URL. Network and
        browser failures are retried by tenacity and then raised to the caller.
        """
        if not is_allowed(url):
            return None
        if self._context is None:
            raise RuntimeError("BrowserClient must be used as a context manager")

        polite_sleep()
        logger.info("Fetching {}", url)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.request_timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=settings.request_timeout_ms)
            except PlaywrightTimeoutError:
                # Some public pages keep analytics/XHR open. DOMContentLoaded is
                # enough for parser snapshots, so continue after logging.
                logger.warning("networkidle timeout for {}; using DOMContentLoaded snapshot", url)
            html = page.content()
            final_url = page.url
            logger.info("Fetched {} bytes from {}", len(html), final_url)
            return FetchResult(url=url, html=html, final_url=final_url)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            logger.exception("Fetch failed for {}: {}", url, exc)
            raise
        finally:
            page.close()
