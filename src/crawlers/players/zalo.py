"""Zalo / Zalopay / Zalo OA player crawlers."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger

from src.crawlers.base import BaseCrawler
from src.crawlers.players._spa import PlayerBlogCrawler
from src.storage.models import ArticleType, RawArticle, Scope, SourceType, Status
from src.utils.date_utils import now_utc, within_window
from src.utils.debug_dump import dump_html


class ZaloPayNews(PlayerBlogCrawler):
    name = "zalopay_news"
    base_url = "https://zalopay.vn/tin-tuc"
    domain_prefix = "https://zalopay.vn"
    url_substring = "/tin-tuc/"
    # Article URLs: /tin-tuc/<slug>; section landing is /tin-tuc itself
    article_url_re = re.compile(r"/tin-tuc/[a-z0-9\-]{6,}")
    block_paths = {"/tin-tuc"}
    player = "Zalo"


class ZaloPayPromo(PlayerBlogCrawler):
    name = "zalopay_promo"
    base_url = "https://zalopay.vn/khuyen-mai"
    domain_prefix = "https://zalopay.vn"
    url_substring = "/khuyen-mai/"
    article_url_re = re.compile(r"/khuyen-mai/[a-z0-9\-]{6,}")
    block_paths = {"/khuyen-mai"}
    player = "Zalo"


class ZaloOANews(BaseCrawler):
    """oa.zalo.me is a Next.js app — the news list is server-rendered
    only inside the __NEXT_DATA__ JSON (no <a> article links exist).
    Parse that JSON directly instead of scraping anchors.
    """

    name = "zalo_oa_news"
    base_url = "https://oa.zalo.me/home/resources/news"
    source_type = "website"
    scope = "domestic"
    type_ = "players_movement"
    player = "Zalo"

    def __init__(self, window_days: int = 7):
        super().__init__()
        self.window_days = window_days
        self._cache: dict[str, dict] = {}

    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        from src.utils.playwright_fetch import fetch_html

        html = await fetch_html(self.base_url) or await self.fetch(
            client, self.base_url
        )
        dump_html(self.name, 0, self.base_url, html)
        if not html:
            return []
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S
        )
        if not m:
            logger.warning("[{}] __NEXT_DATA__ not found", self.name)
            return []
        try:
            data = json.loads(m.group(1))
            items = data["props"]["pageProps"]["resp"]["data"]
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("[{}] cannot parse NEXT_DATA: {}", self.name, e)
            return []
        urls: list[str] = []
        for it in items:
            aid = str(it.get("articleId") or "").strip()
            if not aid:
                continue
            url = f"https://oa.zalo.me/home/resources/news/{aid}"
            self._cache[url] = it
            urls.append(url)
        return urls

    async def parse_article(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[RawArticle]:
        it = self._cache.get(url)
        if not it:
            return None
        title = (it.get("title") or "").strip()
        if not title:
            return None
        published = None
        ts = it.get("createdAt")
        if ts:
            try:
                published = datetime.fromtimestamp(
                    int(ts) / 1000, tz=timezone.utc
                )
            except (ValueError, TypeError, OSError):
                published = None
        # Priority-0 player: drop only when an explicit date is stale.
        if published is not None and not within_window(
            published, self.window_days
        ):
            return None
        return RawArticle(
            id=RawArticle.make_id(url),
            crawled_at=now_utc(),
            source=self.name,
            source_type=SourceType(self.source_type),
            url=url,
            title_original=title,
            content_snippet=(it.get("description") or "").strip(),
            published_date=published,
            type=ArticleType(self.type_),
            player=self.player,
            scope=Scope(self.scope),
            status=Status.NEW,
        )
