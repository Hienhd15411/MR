"""Minimal Playwright wrapper used as fallback when httpx is blocked.

Imported lazily — Playwright is heavy and not needed for pure-RSS runs.
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from src.utils.anti_bot import random_user_agent


async def fetch_html(url: str, timeout_ms: int = 25_000) -> Optional[str]:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.warning("Playwright is not installed; cannot fall back for {}", url)
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random_user_agent())
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Allow late-rendered content to settle.
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                html = await page.content()
                return html
            finally:
                await browser.close()
    except Exception as e:
        logger.warning("Playwright failed for {}: {}", url, e)
        return None
