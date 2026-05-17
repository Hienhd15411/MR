"""Generic HTML listing crawler — Section 1 "HTML scraping" method.

Fetches a listing/category page (httpx → Playwright fallback), extracts
candidate article links, then fetches each article for title / body /
publish_date. Designed for news sites without a clean RSS feed
(OpenAI, Meta, SCMP topic pages, Sensor Tower, Tech in Asia, Luật VN,
The Information, VNEconomy sections).

Heuristics keep it resilient:
  - article link = same-host <a> whose anchor text has >= 5 words and
    whose href has >= 2 path segments and is not a nav/category page
  - body via src.crawlers.players._spa._extract_body_text
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.config.settings import CRAWL_WINDOW_DAYS
from src.crawlers.base import BaseCrawler
from src.crawlers.players._spa import _extract_body_text, _looks_like_cta_or_nav
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)
from src.utils.date_utils import extract_published, now_utc, within_window

_NAV_PATH_RE = re.compile(
    r"/(category|tag|topics?|author|about|contact|privacy|terms|login|"
    r"signin|subscribe|rss|feed|search|page)\b", re.IGNORECASE
)


class HtmlListingCrawler(BaseCrawler):
    def __init__(
        self,
        name: str,
        list_url: str,
        *,
        scope: str = "domestic",
        type_: str = "market_pulse",
        source_type: str = "news",
        player: Optional[str] = None,
        window_days: int = CRAWL_WINDOW_DAYS,
        max_items: int = 40,
    ) -> None:
        super().__init__()
        self.name = name
        self.base_url = list_url
        self.list_url = list_url
        self.scope = scope
        self.type_ = type_
        self.source_type = source_type
        self.player = player
        self.window_days = window_days
        self.max_items = max_items
        self._host = urlsplit(list_url).netloc
        self._cache: dict[str, dict] = {}

    async def _fetch_spa(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        html = await self.fetch(client, url)
        if html and "<a" in html.lower() and len(html) > 4000:
            return html
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] listing empty, Playwright for {}", self.name, url)
        return await fetch_html(url)

    def _is_article_link(self, href: str, text: str) -> bool:
        if not href or not text:
            return False
        sp = urlsplit(href)
        if sp.netloc and sp.netloc != self._host:
            return False
        path = sp.path.rstrip("/")
        if not path or path.count("/") < 1:
            return False
        if _NAV_PATH_RE.search(path):
            return False
        if _looks_like_cta_or_nav(text):
            return False
        if len(text.split()) < 5:
            return False
        return True

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        html = await self._fetch_spa(client, self.list_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if href.startswith("/"):
                href = f"{urlsplit(self.list_url).scheme}://{self._host}{href}"
            if not self._is_article_link(href, text):
                continue
            if href not in self._cache:
                self._cache[href] = {"title": text}
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
            body = _extract_body_text(soup)
            if body:
                snippet = body[:500]
            else:
                desc = soup.find("meta", attrs={"name": "description"})
                if desc and desc.get("content"):
                    snippet = desc["content"]
            published = extract_published(soup, url)

        if not title or _looks_like_cta_or_nav(title):
            return None
        # Strict last-N-days window: an article whose publish date cannot be
        # established is treated as out-of-window so stale posts never leak
        # into the weekly Database.
        if published is None or not within_window(published, self.window_days):
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
