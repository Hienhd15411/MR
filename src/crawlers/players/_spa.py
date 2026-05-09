"""Generic Player-blog SPA crawler.

Most player newsrooms (ZaloPay, ZaloOA, Shopee seller, TikTok Shop,
Grab Merchant, MoMo, Traveloka) are JS-heavy SPAs that return empty
HTML to httpx. This base class:

  1. Tries httpx first (cheap path, in case static HTML ships)
  2. Falls back to Playwright if HTML looks empty
  3. Extracts links matching a configurable URL pattern
  4. Best-effort article enrichment from the detail page

Each player subclass just configures:
  - LIST_URL(s)
  - URL_PATTERN (regex / startswith) for valid article links
  - LIST_BLOCKLIST (URLs that look like article links but are nav)
"""
from __future__ import annotations

import re
from typing import Optional, Pattern

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.config.settings import CRAWL_WINDOW_DAYS
from src.crawlers.base import BaseCrawler
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)
from src.utils.date_utils import now_utc, parse_date, within_window


class PlayerBlogCrawler(BaseCrawler):
    """Subclass + override class attributes."""

    name: str
    base_url: str  # primary list URL
    list_urls: list[str] = []  # additional list pages (optional)
    url_substring: str = "/"  # link must contain this
    article_url_re: Pattern[str] = re.compile(r".*")
    block_paths: set[str] = set()
    domain_prefix: str = ""  # absolute prefix for relative hrefs
    source_type: str = "website"
    type_: str = "players_movement"
    scope: str = "domestic"
    player: str = ""

    def __init__(self, max_items: int = 30, window_days: int = CRAWL_WINDOW_DAYS):
        super().__init__()
        self.max_items = max_items
        self.window_days = window_days
        self._cache: dict[str, dict] = {}

    # ---- URL / link helpers --------------------------------------------

    def _is_article_url(self, href: str) -> bool:
        if not href:
            return False
        if self.url_substring not in href:
            return False
        path = href.split("?")[0].rstrip("/")
        if any(path.endswith(b) for b in self.block_paths):
            return False
        return bool(self.article_url_re.search(path))

    def _absolutise(self, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/") and self.domain_prefix:
            return self.domain_prefix + href
        return href

    # ---- Fetch with SPA fallback ---------------------------------------

    async def _fetch_spa(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        html = await self.fetch(client, url)
        if html and "<a" in html.lower() and len(html) > 5000:
            return html
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] SPA empty, trying Playwright for {}", self.name, url)
        return await fetch_html(url)

    # ---- Crawler interface ---------------------------------------------

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        all_pages = [self.base_url] + list(self.list_urls)
        urls: list[str] = []
        for list_url in all_pages:
            html = await self._fetch_spa(client, list_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = self._absolutise(a["href"])
                if not self._is_article_url(href):
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
