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
    # ISO 8601 is always year-first; parse it directly so the DMY default
    # below (correct for Vietnamese DD/MM strings) cannot mis-swap it.
    iso = text.strip().replace("Z", "+00:00")
    if re.match(r"^\d{4}-\d{2}-\d{2}([T ]\d|$)", iso):
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    settings = {
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TO_TIMEZONE": "UTC",
        "DATE_ORDER": "DMY",
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


def date_from_text(text: str) -> Optional[datetime]:
    """Recover a date from promo phrasing in title/snippet text.

    Player-blog promo posts ("[15.5 - 31.5]", "áp dụng đến 31/5/2026")
    rarely expose a machine-readable publish date, but the active promo
    window in the text is a reliable recency proxy. Prefers the end date
    (promo still valid until then) and falls back to the start date.
    """
    if not text:
        return None
    from src.utils.promo_dates import extract_promo_dates

    start, end = extract_promo_dates(text)
    for s in (end, start):
        if not s:
            continue
        try:
            d, m, y = (int(x) for x in s.split("/"))
            return datetime(y, m, d, tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


_VI_MONTH = r"(?:tháng|thg\.?)\s*\d{1,2}"
_EN_MONTH = (
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
)
_SCAN_RES = [
    re.compile(r"\b20\d{2}-\d{1,2}-\d{1,2}\b"),                       # ISO
    re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]20\d{2}\b"),             # DD/MM/YYYY
    re.compile(rf"ngày\s+\d{{1,2}}\s+{_VI_MONTH}\s+năm\s+20\d{{2}}", re.I),
    re.compile(rf"\d{{1,2}}\s+{_VI_MONTH}(?:[,\s]+20\d{{2}})?", re.I),
    re.compile(rf"{_EN_MONTH}\s+\d{{1,2}},?\s+20\d{{2}}", re.I),
    re.compile(rf"\d{{1,2}}\s+{_EN_MONTH},?\s+20\d{{2}}", re.I),
    re.compile(r"\b[0-3]?\d[/.][01]?\d\b"),                           # DD/MM (no yr)
]


def scan_date(text: str) -> Optional[datetime]:
    """Find the first plausible calendar date anywhere in free text.

    Used for player-blog listing cards / detail bodies that print a date
    like "15/05/2026", "15 tháng 5, 2026" or "May 15, 2026" but expose no
    machine-readable metadata. More permissive than date_from_text (which
    only understands promo phrasing); strict enough that promo amounts
    ("500.000đ", "8.686Đ") do not match.
    """
    if not text:
        return None
    for rx in _SCAN_RES:
        m = rx.search(text)
        if not m:
            continue
        dt = parse_date(m.group(0))
        if dt and 2000 <= dt.year <= 2100:
            return dt
    return None


def listing_date_near(anchor, max_up: int = 4) -> Optional[datetime]:
    """Extract a publish date from the DOM card surrounding a list anchor.

    Player blog index pages render each post as a card containing both the
    link and a small date element. Walk a few ancestors up from the <a>
    and look for a <time> tag, a date-classed element, or a short text
    node that scans as a date. Returns the closest match.
    """
    node = getattr(anchor, "parent", None)
    for _ in range(max_up):
        if node is None:
            break
        t = node.find("time") if hasattr(node, "find") else None
        if t is not None:
            dt = parse_date(
                t.get("datetime") or t.get_text(" ", strip=True)
            )
            if dt:
                return dt
        if hasattr(node, "find_all"):
            for el in node.find_all(
                attrs={"class": re.compile(r"date|time|publish|ngay", re.I)}
            ):
                txt = el.get_text(" ", strip=True)
                if 0 < len(txt) <= 40:
                    dt = scan_date(txt)
                    if dt:
                        return dt
            txt = node.get_text(" ", strip=True)
            if len(txt) <= 200:
                dt = scan_date(txt)
                if dt:
                    return dt
        node = getattr(node, "parent", None)
    return None


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
