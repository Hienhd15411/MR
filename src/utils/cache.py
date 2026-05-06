"""Simple disk cache for HTTP responses.

Used by BaseCrawler.fetch so dev iterations don't re-hit upstream sites.
Disabled in CI by setting CRAWL_CACHE=0; default-on locally.

Cache key = sha1(url). TTL = 24h.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

from src.config.settings import CACHE_DIR

TTL_SECONDS = 24 * 3600


def _enabled() -> bool:
    return os.getenv("CRAWL_CACHE", "1") not in ("0", "false", "no")


def _path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.html"


def read(url: str) -> Optional[str]:
    if not _enabled():
        return None
    p = _path_for(url)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > TTL_SECONDS:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def write(url: str, body: str) -> None:
    if not _enabled() or not body:
        return
    p = _path_for(url)
    try:
        p.write_text(body, encoding="utf-8")
    except OSError:
        pass


def clear() -> int:
    n = 0
    for f in CACHE_DIR.glob("*.html"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n
