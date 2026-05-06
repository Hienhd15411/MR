from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Sequence

import httpx
from loguru import logger

from src.crawlers.base import BaseCrawler
from src.crawlers.factory import build_crawlers_from_yaml
from src.pipeline.filter import apply_filter
from src.storage.excel_sink import write_excel
from src.storage.markdown_sink import write_markdown
from src.storage.models import RawArticle, Status

MAX_CONCURRENCY = 5


def build_crawlers() -> list[BaseCrawler]:
    """Build all crawlers from sources.yaml."""
    return build_crawlers_from_yaml()


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


def run_pipeline(
    write_to_sheet: bool = False,
    markdown_path: Optional[Path] = None,
    excel_path: Optional[Path] = None,
) -> dict:
    crawlers = build_crawlers()
    articles = asyncio.run(crawl_all(crawlers))
    articles = apply_filter(articles)
    n_filtered = sum(1 for a in articles if a.status == Status.FILTERED_OUT)
    summary: dict = {
        "crawled": len(articles),
        "kept": len(articles) - n_filtered,
        "filtered_out": n_filtered,
    }
    if markdown_path is not None:
        n = write_markdown(markdown_path, articles)
        logger.info("Wrote {} articles to {}", n, markdown_path)
        summary["markdown_path"] = str(markdown_path)
        summary["markdown_count"] = n
    if excel_path is not None:
        n = write_excel(excel_path, articles)
        logger.info("Wrote {} articles to {}", n, excel_path)
        summary["excel_path"] = str(excel_path)
        summary["excel_count"] = n
    if write_to_sheet and articles:
        # Lazy import: avoid pulling gspread/cryptography unless actually needed.
        from src.storage.sheets import SheetsClient

        client = SheetsClient.from_env()
        summary["sheet_written"] = client.append_raw(articles)
    return summary
