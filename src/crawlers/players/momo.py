"""MoMo Newsroom crawler (https://momo.vn/tin-tuc).

The newsroom is a SPA — httpx returns mostly empty HTML. We try httpx first
(cheap path, in case a static index ships), then fall back to Playwright.
Selectors are intentionally permissive so a layout tweak does not crash.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.crawlers.base import BaseCrawler
from src.utils.debug_dump import dump_html
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)
from src.config.settings import CRAWL_WINDOW_DAYS
from src.utils.date_utils import (
    date_from_text,
    extract_published,
    listing_date_near,
    now_utc,
    scan_date,
    within_window,
)


LIST_URL = "https://momo.vn/tin-tuc"
# Section landing pages each list more articles than the /tin-tuc root.
# Hitting all three multiplies voucher / promo coverage 3-5x.
LIST_URLS_EXTRA = [
    "https://momo.vn/tin-tuc/khuyen-mai",
    "https://momo.vn/tin-tuc/thong-bao",
    "https://momo.vn/tin-tuc/tin-tuc-su-kien",
]

# Real MoMo article URLs end with `-<numeric_id>`, e.g.
# /tin-tuc/thong-bao/giai-ma-tu-khoa-rinh-goi-nang-cap-youtube-icloud-8704.
# Section landing pages (/tin-tuc/thong-bao, /tin-tuc/cong-dong, …) don't
# have a numeric suffix and must be skipped.
_ARTICLE_ID_RE = re.compile(r"-\d+/?$")
_SECTION_BLOCKLIST = {
    "/tin-tuc",
    "/tin-tuc/thong-cao-bao-chi",
    "/tin-tuc/hinh-anh-video",
    "/tin-tuc/khuyen-mai",
    "/tin-tuc/cong-dong",
    "/tin-tuc/thong-bao",
    "/tin-tuc/tin-tuc-su-kien",
    "/tin-tuc/thong-cao",
    "/tin-tuc/thu-vien",
}


def _looks_like_news_link(href: str) -> bool:
    """Real article URLs only — skip section landing pages."""
    if not href:
        return False
    if "/tin-tuc/" not in href and not href.endswith("/tin-tuc"):
        return False
    path = href.split("?")[0].rstrip("/")
    if any(path.endswith(b) for b in _SECTION_BLOCKLIST):
        return False
    if not _ARTICLE_ID_RE.search(path):
        return False
    return True


class MoMoNewsroom(BaseCrawler):
    name = "momo_newsroom"
    base_url = LIST_URL
    source_type = "website"
    scope = "domestic"
    type_ = "players_movement"
    player = "MoMo"

    def __init__(self, max_items: int = 60, window_days: int = CRAWL_WINDOW_DAYS):
        super().__init__()
        self.max_items = max_items
        self.window_days = window_days
        self._cache: dict[str, dict] = {}

    async def _fetch_spa(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """momo.vn renders only ~3 posts server-side; the rest lazy-load
        on scroll. Always drive a scrolling headless browser."""
        from src.utils.playwright_fetch import fetch_html

        html = await fetch_html(url, scroll=True)
        if html:
            return html
        return await self.fetch(client, url)

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        urls: list[str] = []
        for i, list_url in enumerate([self.base_url] + LIST_URLS_EXTRA):
            html = await self._fetch_spa(client, list_url)
            dump_html(self.name, i, list_url, html)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not _looks_like_news_link(href):
                    continue
                if href.startswith("/"):
                    href = "https://momo.vn" + href
                if href.rstrip("/") == LIST_URL.rstrip("/"):
                    continue
                title = a.get_text(" ", strip=True)
                if title and href not in self._cache:
                    self._cache[href] = {
                        "title": title,
                        "listing_date": listing_date_near(a),
                    }
                if href not in urls:
                    urls.append(href)
        return urls[: self.max_items]

    async def parse_article(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[RawArticle]:
        meta = self._cache.get(url, {})
        title = meta.get("title", "")
        snippet = ""
        published = None

        # Try to enrich with detail page (best-effort).
        html = await self.fetch(client, url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            if h1 and h1.get_text(strip=True):
                title = h1.get_text(strip=True)
            # Body content first (voucher mechanics live in body, not meta).
            from src.crawlers.players._spa import _extract_body_text
            body = _extract_body_text(soup)
            if body:
                snippet = body[:500]
            else:
                desc = soup.find("meta", attrs={"name": "description"})
                if desc and desc.get("content"):
                    snippet = desc["content"]
            published = extract_published(soup, url)

        if not title:
            return None
        if published is None:
            published = scan_date(snippet)
        if published is None:
            published = date_from_text(f"{title} {snippet}")
        if published is None:
            published = meta.get("listing_date")
        # Priority-0 player blog: spec says always keep. Drop only when an
        # explicit date proves the post is older than the window; undated
        # posts are kept (the listing is newest-first and capped).
        if published is not None and not within_window(published, self.window_days):
            return None

        return RawArticle(
            id=RawArticle.make_id(url),
            crawled_at=now_utc(),
            source=self.name,
            source_type=SourceType(self.source_type),
            url=url,
            title_original=title,
            content_snippet=snippet,
            published_date=published,
            type=ArticleType(self.type_),
            player=self.player,
            scope=Scope(self.scope),
            status=Status.NEW,
        )
