from __future__ import annotations

import asyncio
from typing import Sequence

import httpx
from loguru import logger

from src.crawlers.base import BaseCrawler
from src.crawlers.news.vnexpress import VnExpressSoHoa
from src.storage.models import RawArticle
from src.storage.sheets import SheetsClient

MAX_CONCURRENCY = 5


def build_crawlers() -> list[BaseCrawler]:
    """Iter 1: only VnExpress so-hoa. Iter 2 will add the rest."""
    return [VnExpressSoHoa()]


async def _run_one(crawler: BaseCrawler, sem: asyncio.Semaphore,
                   client: httpx.AsyncClient) -> list[RawArticle]:
    async with sem:
        try:
            return await crawler.run(client)
        except Exception as e:
            logger.exception("[{}] crashed: {}", crawler.name, e)
            return []


async def crawl_all(crawlers: Sequence[BaseCrawler]) -> list[RawArticle]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [_run_one(c, sem, client) for c in crawlers]
        results = await asyncio.gather(*tasks)
    flat = [a for batch in results for a in batch]
    logger.info("Crawl produced {} total articles", len(flat))
    return flat


def run_pipeline(write_to_sheet: bool = True) -> dict:
    crawlers = build_crawlers()
    articles = asyncio.run(crawl_all(crawlers))
    written = 0
    if write_to_sheet and articles:
        client = SheetsClient.from_env()
        written = client.append_raw(articles)
    return {"crawled": len(articles), "written": written}
