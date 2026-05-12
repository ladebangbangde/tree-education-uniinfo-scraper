"""Simple polite request pacing."""
from __future__ import annotations

import random
import time
from ..config import settings
from ..logger import logger


def polite_sleep() -> None:
    delay = random.uniform(settings.request_min_delay, settings.request_max_delay)
    logger.info(f"Sleeping {delay:.2f}s before request")
    time.sleep(delay)
