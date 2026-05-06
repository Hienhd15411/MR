"""MoMo Newsroom crawler (https://momo.vn/tin-tuc).

The newsroom is a SPA — httpx returns mostly empty HTML. We try httpx first
(cheap path, in case a static index ships), then fall back to Playwright.
Selectors are intentionally permissive so a layout tweak does not crash.
"""
from __future__ import annotations

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
from src.utils.date_utils import now_utc, parse_date


LIST_URL = "https://momo.vn/tin-tuc"


def _looks_like_news_link(href: str) -> bool:
    if not href:
        return False
    if href.startswith("/tin-tuc/") and len(href) > len("/tin-tuc/") + 1:
        return True
    if "momo.vn/tin-tuc/" in href:
        return True
    return False


class MoMoNewsroom(BaseCrawler):
    name = "momo_newsroom"
    base_url = LIST_URL
    source_type = "website"
    scope = "domestic"
    type_ = "players_movement"
    player = "MoMo"

    def __init__(self, max_items: int = 30):
        super().__init__()
        self.max_items = max_items
        self._cache: dict[str, dict] = {}

    async def _fetch_with_fallback(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[str]:
        html = await self.fetch(client, url)
        if html and "<a" in html.lower():
            return html
        # Fallback to Playwright
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] httpx empty/blocked, trying Playwright for {}", self.name, url)
        return await fetch_html(url)

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        html = await self._fetch_with_fallback(client, self.base_url)
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
