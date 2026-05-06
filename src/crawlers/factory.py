"""Build BaseCrawler instances from `src/config/sources.yaml`.

RSS sources are instantiated directly via RSSCrawler.
Custom sources (Playwright players) reference a `module: dotted.path:ClassName`
which is imported lazily so the optional Playwright dependency is only loaded
when actually needed.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from src.config.settings import SOURCES_YAML
from src.crawlers.base import BaseCrawler
from src.crawlers.rss import RSSCrawler


def _load_class(dotted: str) -> type:
    module_name, _, class_name = dotted.partition(":")
    if not module_name or not class_name:
        raise ValueError(f"Invalid module spec: {dotted!r} (expected 'pkg.mod:Class')")
    mod = importlib.import_module(module_name)
    return getattr(mod, class_name)


def _build_one(entry: dict[str, Any]) -> BaseCrawler | None:
    kind = (entry.get("crawler") or "rss").lower()
    key = entry["key"]
    try:
        if kind == "rss":
            return RSSCrawler(
                name=key,
                rss_url=entry["rss_url"],
                scope=entry.get("scope", "domestic"),
                type_=entry.get("type", "market_pulse"),
                source_type=entry.get("source_type",
                                      "website" if entry.get("type") == "players_movement"
                                      else "news"),
                player=entry.get("player"),
            )
        if kind == "playwright":
            cls = _load_class(entry["module"])
            return cls()
        logger.warning("Unknown crawler kind {!r} for {}", kind, key)
        return None
    except Exception as e:
        logger.error("Failed to build crawler {}: {}", key, e)
        return None


def build_crawlers_from_yaml(path: Path = SOURCES_YAML) -> list[BaseCrawler]:
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    crawlers: list[BaseCrawler] = []
    for section in ("news", "players"):
        for entry in cfg.get(section) or []:
            c = _build_one(entry)
            if c is not None:
                crawlers.append(c)
    logger.info("Loaded {} crawlers from {}", len(crawlers), path)
    return crawlers
