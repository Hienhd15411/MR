from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

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


@dataclass
class RSSItem:
    url: str
    title: str
    description: str
    published: Optional[datetime]


def parse_rss(xml_text: str) -> list[RSSItem]:
    """Lightweight RSS 2.0 / Atom-ish parser using BeautifulSoup XML mode.

    Robust enough for major news feeds without adding feedparser.
    """
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        items = soup.find_all("entry")  # Atom fallback
    out: list[RSSItem] = []
    for it in items:
        link_el = it.find("link")
        if link_el is None:
            continue
        href = link_el.get_text(strip=True) or link_el.get("href", "")
        if not href:
            continue
        title = (it.find("title").get_text(strip=True) if it.find("title") else "") or ""
        desc_el = it.find("description") or it.find("summary")
        description = desc_el.get_text(strip=True) if desc_el else ""
        # Strip embedded HTML from description
        if description and "<" in description:
            description = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)
        date_el = it.find("pubDate") or it.find("published") or it.find("updated")
        published = parse_date(date_el.get_text(strip=True)) if date_el else None
        out.append(RSSItem(url=href, title=title, description=description, published=published))
    return out


class RSSCrawler(BaseCrawler):
    """Crawl an RSS/Atom feed; details optionally enriched from article HTML."""

    rss_url: str
    detail_selector: Optional[str] = None  # CSS selector for <h1> on detail page (optional)

    def __init__(
        self,
        name: str,
        rss_url: str,
        *,
        scope: str = "domestic",
        type_: str = "market_pulse",
        source_type: str = "news",
        player: Optional[str] = None,
        detail_selector: Optional[str] = None,
        window_days: int = CRAWL_WINDOW_DAYS,
        max_items: int = 50,
    ) -> None:
        super().__init__()
        self.name = name
        self.base_url = rss_url
        self.rss_url = rss_url
        self.scope = scope
        self.type_ = type_
        self.source_type = source_type
        self.player = player
        self.detail_selector = detail_selector
        self.window_days = window_days
        self.max_items = max_items
        self._items_cache: list[RSSItem] = []

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        xml = await self.fetch(client, self.rss_url)
        from src.utils.debug_dump import dump_html

        dump_html(self.name, 0, self.rss_url, xml)
        if not xml:
            return []
        items = parse_rss(xml)
        # Strict last-N-days window: an item with no pubDate, or one outside
        # the window, is dropped so stale posts never reach the Database.
        kept: list[RSSItem] = []
        for it in items:
            if not it.published or not within_window(it.published, self.window_days):
                continue
            kept.append(it)
        kept = kept[: self.max_items]
        self._items_cache = kept
        return [it.url for it in kept]

    async def parse_article(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[RawArticle]:
        item = next((i for i in self._items_cache if i.url == url), None)
        if item is None:
            logger.debug("[{}] url not in RSS cache: {}", self.name, url)
            return None
        if not item.title:
            return None
        return RawArticle(
            id=RawArticle.make_id(url),
            crawled_at=now_utc(),
            source=self.name,
            source_type=SourceType(self.source_type),
            url=url,
            title_original=item.title,
            content_snippet=item.description,
            published_date=item.published,
            type=ArticleType(self.type_),
            player=self.player,
            scope=Scope(self.scope),
            status=Status.NEW,
        )
