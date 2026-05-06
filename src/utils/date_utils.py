from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import dateparser


def parse_date(text: str, languages: Optional[list[str]] = None) -> Optional[datetime]:
    """Parse a free-form date string into a UTC-aware datetime.

    Falls back to None when parsing fails. Uses dateparser so that both
    Vietnamese ("Thứ Hai, 6/5/2026, 14:30 (GMT+7)") and English/RFC822
    formats from RSS feeds work.
    """
    if not text:
        return None
    settings = {
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TO_TIMEZONE": "UTC",
    }
    dt = dateparser.parse(text.strip(), languages=languages or ["vi", "en"], settings=settings)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_vn_date(text: str) -> Optional[datetime]:
    return parse_date(text, languages=["vi", "en"])


def within_window(dt: Optional[datetime], days: int) -> bool:
    """True if `dt` is within the last `days` days from now (UTC)."""
    if dt is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return dt >= cutoff


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
