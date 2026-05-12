"""Central logger configuration with a small stdlib fallback for test environments."""
from __future__ import annotations

import importlib.util
import logging
import sys

if importlib.util.find_spec("loguru"):
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    )
else:  # pragma: no cover - used only when optional dependencies are unavailable.
    class _FallbackLogger:
        def __init__(self) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
            self._logger = logging.getLogger("tree_education_uniinfo_scraper")

        def _format(self, message: str, *args) -> str:
            return message.format(*args) if args else message

        def info(self, message: str, *args, **kwargs) -> None:
            self._logger.info(self._format(message, *args))

        def warning(self, message: str, *args, **kwargs) -> None:
            self._logger.warning(self._format(message, *args))

        def exception(self, message: str, *args, **kwargs) -> None:
            self._logger.exception(self._format(message, *args))

        def error(self, message: str, *args, **kwargs) -> None:
            self._logger.error(self._format(message, *args))

    logger = _FallbackLogger()
