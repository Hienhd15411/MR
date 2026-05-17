from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

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


_URL_DATE_RES = [
    re.compile(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:[/-]|\b)"),
    re.compile(r"[-_](20\d{2})(\d{2})(\d{2})[-_.]"),
]


def _date_from_url(url: str) -> Optional[datetime]:
    for rx in _URL_DATE_RES:
        m = rx.search(url or "")
        if m:
            y, mo, d = (int(g) for g in m.groups())
            try:
                return datetime(y, mo, d, tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _walk_jsonld(node: Any) -> Optional[str]:
    if isinstance(node, dict):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            v = node.get(key)
            if isinstance(v, str) and v.strip():
                return v
        for v in node.values():
            found = _walk_jsonld(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _walk_jsonld(v)
            if found:
                return found
    return None


def extract_published(soup, url: str = "") -> Optional[datetime]:
    """Best-effort publish-date extraction from a parsed HTML page.

    Tries, in order: <time datetime>/<time> text, common <meta> tags
    (article:published_time, og:published_time, pubdate, date,
    DC.date.issued), itemprop=datePublished, JSON-LD datePublished, and
    finally a date embedded in the URL path. Returns None only when no
    signal at all is found.
    """
    time_el = soup.find("time")
    if time_el:
        dt = parse_date(time_el.get("datetime") or time_el.get_text(strip=True))
        if dt:
            return dt

    meta_keys = [
        ("property", "article:published_time"),
        ("property", "og:published_time"),
        ("property", "article:modified_time"),
        ("name", "pubdate"),
        ("name", "publishdate"),
        ("name", "date"),
        ("name", "DC.date.issued"),
        ("itemprop", "datePublished"),
    ]
    for attr, val in meta_keys:
        el = soup.find("meta", attrs={attr: val})
        if el and el.get("content"):
            dt = parse_date(el["content"])
            if dt:
                return dt

    ip = soup.find(attrs={"itemprop": "datePublished"})
    if ip:
        dt = parse_date(ip.get("datetime") or ip.get_text(strip=True))
        if dt:
            return dt

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        cand = _walk_jsonld(data)
        if cand:
            dt = parse_date(cand)
            if dt:
                return dt

    return _date_from_url(url)
