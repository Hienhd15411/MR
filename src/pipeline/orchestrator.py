from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import httpx
import yaml
from loguru import logger

from src.crawlers.base import BaseCrawler
from src.crawlers.factory import build_crawlers_from_yaml
from src.pipeline.dedup import deduplicate
from src.pipeline.filter import SOURCES_YAML, apply_filter
from src.pipeline.scoring import apply_scoring
from src.storage.excel_sink import write_excel
from src.storage.markdown_sink import write_markdown
from src.storage.models import RawArticle

MAX_CONCURRENCY = 5


def _priority_map() -> dict[str, int]:
    with SOURCES_YAML.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    out: dict[str, int] = {}
    for section in ("news", "players"):
        for entry in cfg.get(section) or []:
            out[entry["key"]] = int(entry.get("priority", 1))
    return out


def build_crawlers() -> list[BaseCrawler]:
    return build_crawlers_from_yaml()


async def _run_one(crawler, sem, client) -> tuple[str, list[RawArticle], str]:
    async with sem:
        try:
            arts = await crawler.run(client)
            return crawler.name, arts, ""
        except Exception as e:  # noqa: BLE001
            logger.exception("[{}] crashed: {}", crawler.name, e)
            return crawler.name, [], str(e)


async def crawl_all(
    crawlers: Sequence[BaseCrawler],
) -> tuple[list[RawArticle], dict[str, tuple[int, str]]]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async with httpx.AsyncClient(http2=False) as client:
        results = await asyncio.gather(
            *[_run_one(c, sem, client) for c in crawlers]
        )
    flat: list[RawArticle] = []
    per_source: dict[str, tuple[int, str]] = {}
    for name, arts, err in results:
        flat.extend(arts)
        per_source[name] = (len(arts), err)
    logger.info("Crawl produced {} total articles", len(flat))
    return flat, per_source


def run_pipeline(
    write_to_sheet: bool = False,
    markdown_path: Optional[Path] = None,
    excel_path: Optional[Path] = None,
) -> dict:
    started = datetime.now(timezone.utc)
    crawlers = build_crawlers()
    articles, per_source = asyncio.run(crawl_all(crawlers))

    # Attach source priority for dedup keep-rule
    pmap = _priority_map()
    for a in articles:
        a._source_priority = pmap.get(a.source, 1)  # type: ignore[attr-defined]

    # Section 4 — dedup BEFORE filter (priority-aware keep)
    unique, dups = deduplicate(articles)

    # Section 2 — 4-tier filter
    kept, discarded_filter = apply_filter([(a, a.source) for a in unique])
    discarded = dups + discarded_filter

    # Section 3 — basic scoring
    apply_scoring(kept)

    ended = datetime.now(timezone.utc)

    # Audit_Log rows (one per source)
    flagged = sum(1 for a in kept if getattr(a, "_review_flag", False))
    audit_rows = []
    for name, (fetched, err) in sorted(per_source.items()):
        k = sum(1 for a in kept if a.source == name)
        d = sum(1 for a in discarded if a.source == name)
        f = sum(1 for a in kept if a.source == name
                and getattr(a, "_review_flag", False))
        audit_rows.append([
            started.isoformat(), ended.isoformat(), name,
            fetched, k, d, f, err,
        ])

    summary: dict = {
        "crawled": len(articles),
        "unique": len(unique),
        "duplicates": len(dups),
        "kept": len(kept),
        "discarded": len(discarded),
        "flagged_human_review": flagged,
    }

    if excel_path is not None:
        n = write_excel(excel_path, kept, discarded, audit_rows)
        logger.info("Wrote {} kept rows to {}", n, excel_path)
        summary["excel_path"] = str(excel_path)
    if markdown_path is not None:
        n = write_markdown(markdown_path, kept)
        logger.info("Wrote {} rows to {}", n, markdown_path)
        summary["markdown_path"] = str(markdown_path)
    if write_to_sheet and kept:
        from src.storage.sheets import SheetsClient

        client = SheetsClient.from_env()
        summary["sheet_written"] = client.append_raw(kept)
    return summary
