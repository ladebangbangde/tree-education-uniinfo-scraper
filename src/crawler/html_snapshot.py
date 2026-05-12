"""HTML snapshot storage with SHA-256 hashes for traceability."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from ..config import settings


def save_html_snapshot(html: str, source_site: str) -> tuple[str, Path]:
    digest = hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()
    date_path = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    directory = Path(settings.snapshot_dir) / source_site / date_path
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.html"
    if not path.exists():
        path.write_text(html, encoding="utf-8")
    return digest, path
