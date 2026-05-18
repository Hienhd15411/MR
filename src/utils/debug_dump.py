"""Optional raw-HTML dump for debugging player-blog crawlers.

The sandbox has no outbound network, so listing-page DOM can only be
inspected from what the CI runner actually fetched. When MW_DEBUG_DUMP
is set, each crawler writes the fetched listing HTML to output/debug/
so the real markup can be reviewed and selectors fixed from data.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_ENABLED = bool(os.getenv("MW_DEBUG_DUMP"))
_DIR = Path("output/debug")


def dump_html(source: str, idx: int, url: str, html: str | None) -> None:
    if not _ENABLED or not html:
        return
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", source)[:40]
        path = _DIR / f"{safe}-{idx}.html"
        header = f"<!-- source={source} idx={idx} url={url} len={len(html)} -->\n"
        path.write_text(header + html, encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — debug aid must never break a crawl
        pass
