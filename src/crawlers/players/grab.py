"""Grab VN Blog crawler (https://www.grab.com/vn/blog/).

Same hybrid strategy as MoMo: httpx first, Playwright fallback.
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
from src.config.settings import CRAWL_WINDOW_DAYS
from src.utils.date_utils import (
    date_from_text,
    extract_published,
    listing_date_near,
    now_utc,
    scan_date,
    within_window,
)


LIST_URL = "https://www.grab.com/vn/blog/"

# Grab VN blog is organised into category pages. Each one lists that
# section's recent posts — crawl them all, not just the homepage.
_SECTIONS = [
    "driver", "merchant", "food", "mart", "express", "news",
    "passenger", "car", "delivery", "safety", "payment", "story",
]
LIST_URLS = [LIST_URL] + [f"{LIST_URL}{s}/" for s in _SECTIONS]

# A category/landing slug is NOT an article. Real posts have a long,
# hyphenated slug (e.g. /vn/blog/grab-uu-dai-thang-5-2026).
_NON_POST_SLUGS = set(_SECTIONS) | {
    "vn", "blog", "category", "tag", "author", "page", "search",
}


def _post_slug(href: str) -> Optional[str]:
    if not href or "/vn/blog/" not in href:
        return None
    after = href.split("?")[0].split("#")[0].split("/vn/blog/", 1)[1].strip("/")
    if not after:
        return None
    return after.split("/")[-1]


def _looks_like_post(href: str) -> bool:
    slug = _post_slug(href)
    if not slug or slug in _NON_POST_SLUGS:
        return False
    # Article slugs are hyphenated and reasonably long; category pages
    # ("driver", "merchant") are single short words and get filtered above.
    return "-" in slug and len(slug) >= 12


class GrabVNBlog(BaseCrawler):
    name = "grab_vn_blog"
    base_url = LIST_URL
    source_type = "website"
    scope = "domestic"
    type_ = "players_movement"
    player = "Grab"

    def __init__(self, max_items: int = 30, window_days: int = CRAWL_WINDOW_DAYS):
        super().__init__()
        self.max_items = max_items
        self.window_days = window_days
        self._cache: dict[str, dict] = {}

    async def _fetch_spa(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """SPAs may return 200 with empty shell HTML; force Playwright in that case."""
        html = await self.fetch(client, url)
        if html and len(html) > 5000:
            return html
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] HTML looks empty, forcing Playwright for {}", self.name, url)
        return await fetch_html(url)

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        urls: list[str] = []
        for list_url in LIST_URLS:
            html = await self._fetch_spa(client, list_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not _looks_like_post(href):
                    continue
                if href.startswith("/"):
                    href = "https://www.grab.com" + href
                title = a.get_text(" ", strip=True)
                if title:
                    self._cache.setdefault(
                        href,
                        {"title": title, "listing_date": listing_date_near(a)},
                    )
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
        # Priority-0 player blog: keep undated posts (newest-first, capped);
        # drop only when an explicit date is older than the window.
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
