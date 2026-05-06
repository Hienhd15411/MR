from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx
from loguru import logger

from src.storage.models import RawArticle
from src.utils import cache as html_cache
from src.utils.anti_bot import polite_delay, random_user_agent


# HTTP statuses that warrant the Playwright fallback (anti-bot blocks).
_BLOCK_STATUSES = (403, 429, 503)


class BaseCrawler(ABC):
    """Subclasses crawl one logical source and emit RawArticle objects.

    fetch() implements the spec's anti-bot policy:
      1. httpx + rotated User-Agent + 2-5s polite delay
      2. on 403/429/503 (or network error) → fall back to headless Playwright
      3. on Playwright failure → return None, the pipeline skips this URL
      4. successful responses are cached on disk for 24h (CRAWL_CACHE=0 to disable)
    """

    name: str
    base_url: str
    source_type: str = "news"
    scope: str = "domestic"
    type_: str = "market_pulse"
    player: Optional[str] = None

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        cached = html_cache.read(url)
        if cached is not None:
            logger.debug("[{}] cache hit for {}", self.name, url)
            return cached

        body = await self._fetch_httpx(client, url)
        if body is None:
            body = await self._fetch_playwright(url)
        if body is not None:
            html_cache.write(url, body)
        return body

    async def _fetch_httpx(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            await polite_delay()
            resp = await client.get(
                url,
                headers={
                    "User-Agent": random_user_agent(),
                    "Accept-Language": "vi,en;q=0.8",
                },
                timeout=self.timeout,
                follow_redirects=True,
            )
        except Exception as e:
            logger.warning("[{}] httpx error {}: {}", self.name, url, e)
            return None
        if resp.status_code in _BLOCK_STATUSES:
            logger.warning(
                "[{}] httpx blocked {} on {} — will try Playwright fallback",
                self.name, resp.status_code, url,
            )
            return None
        if resp.status_code >= 400:
            logger.warning("[{}] httpx HTTP {} on {}", self.name, resp.status_code, url)
            return None
        return resp.text

    async def _fetch_playwright(self, url: str) -> Optional[str]:
        # Lazy import so RSS-only runs don't pay the Playwright cost.
        from src.utils.playwright_fetch import fetch_html

        logger.info("[{}] trying Playwright for {}", self.name, url)
        body = await fetch_html(url)
        if body is None:
            logger.warning("[{}] Playwright also failed for {} — skipping", self.name, url)
        return body

    @abstractmethod
    async def list_article_urls(self, client: httpx.AsyncClient) -> list[str]:
        ...

    @abstractmethod
    async def parse_article(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[RawArticle]:
        ...

    async def run(self, client: httpx.AsyncClient) -> list[RawArticle]:
        out: list[RawArticle] = []
        try:
            urls = await self.list_article_urls(client)
        except Exception as e:
            logger.error("[{}] list_article_urls failed: {}", self.name, e)
            return out
        logger.info("[{}] discovered {} URLs", self.name, len(urls))
        for url in urls:
            try:
                art = await self.parse_article(client, url)
                if art is not None:
                    out.append(art)
            except Exception as e:
                logger.warning("[{}] parse_article {} failed: {}", self.name, url, e)
        logger.info("[{}] produced {} articles", self.name, len(out))
        return out
