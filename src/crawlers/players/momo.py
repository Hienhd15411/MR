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
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)
from src.config.settings import CRAWL_WINDOW_DAYS
from src.utils.date_utils import now_utc, parse_date, within_window


LIST_URL = "https://momo.vn/tin-tuc"

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

    def __init__(self, max_items: int = 30, window_days: int = CRAWL_WINDOW_DAYS):
        super().__init__()
        self.max_items = max_items
        self.window_days = window_days
        self._cache: dict[str, dict] = {}

    async def _fetch_spa(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """SPAs may return 200 with empty shell HTML; force Playwright in that case."""
        html = await self.fetch(client, url)
        if html and "<a" in html.lower() and len(html) > 5000:
            return html
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] HTML looks empty, forcing Playwright for {}", self.name, url)
        return await fetch_html(url)

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        html = await self._fetch_spa(client, self.base_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _looks_like_news_link(href):
                if href.startswith("/"):
                    href = "https://momo.vn" + href
                if href.rstrip("/") == LIST_URL.rstrip("/"):
                    continue
                title = a.get_text(" ", strip=True)
                if title and href not in self._cache:
                    self._cache[href] = {"title": title}
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
            desc = soup.find("meta", attrs={"name": "description"})
            if desc and desc.get("content"):
                snippet = desc["content"]
            time_el = soup.find("time")
            if time_el:
                published = parse_date(
                    time_el.get("datetime") or time_el.get_text(strip=True)
                )

        if not title:
            return None
        # Spec: only "7 ngày gần nhất". Drop articles known to be older.
        # If we couldn't parse a date, keep the article (listing pages are
        # ordered newest-first and we already cap to max_items).
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
