from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx
from loguru import logger

from src.storage.models import RawArticle
from src.utils.anti_bot import polite_delay, random_user_agent


class BaseCrawler(ABC):
    """Subclasses crawl one logical source and emit RawArticle objects."""

    name: str
    base_url: str
    source_type: str = "news"
    scope: str = "domestic"
    type_: str = "market_pulse"
    player: Optional[str] = None

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            await polite_delay()
            resp = await client.get(
                url,
                headers={"User-Agent": random_user_agent(), "Accept-Language": "vi,en;q=0.8"},
                timeout=self.timeout,
                follow_redirects=True,
            )
        except Exception as e:
            logger.warning("[{}] fetch error {}: {}", self.name, url, e)
            return None
        if resp.status_code in (403, 429, 503):
            logger.warning("[{}] blocked {} on {}", self.name, resp.status_code, url)
            return None
        if resp.status_code >= 400:
            logger.warning("[{}] HTTP {} on {}", self.name, resp.status_code, url)
            return None
        return resp.text

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
