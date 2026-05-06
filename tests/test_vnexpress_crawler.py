from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.crawlers.news.vnexpress import VnExpressSoHoa
from src.crawlers.rss import parse_rss

FIXTURE = Path(__file__).parent / "fixtures" / "vnexpress_rss.xml"


def test_parse_rss_extracts_items_and_strips_html():
    xml = FIXTURE.read_text(encoding="utf-8")
    items = parse_rss(xml)
    assert len(items) == 3
    first = items[0]
    assert first.title == "OpenAI ra mắt mô hình GPT mới"
    assert first.url.startswith("https://vnexpress.net/openai-ra-mat")
    assert "<" not in first.description
    assert first.published is not None
    assert first.published.tzinfo is not None


@pytest.mark.asyncio
async def test_vnexpress_crawler_end_to_end(monkeypatch):
    crawler = VnExpressSoHoa()
    # Make the window huge so dated fixture items aren't filtered.
    crawler.window_days = 365 * 10

    fixture_xml = FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(self, client, url):
        return fixture_xml

    monkeypatch.setattr(VnExpressSoHoa, "fetch", fake_fetch, raising=True)

    articles = await crawler.run(client=None)  # client unused due to fake_fetch
    assert len(articles) == 3
    titles = {a.title_original for a in articles}
    assert "OpenAI ra mắt mô hình GPT mới" in titles
    # All articles must have IDs and required enums populated.
    for a in articles:
        assert len(a.id) == 16
        assert a.source == "vnexpress_sohoa"
        assert a.scope.value == "domestic"
        assert a.type.value == "market_pulse"
        assert a.status.value == "new"


@pytest.mark.asyncio
async def test_vnexpress_window_filters_old_items(monkeypatch):
    crawler = VnExpressSoHoa()
    crawler.window_days = 7

    fixture_xml = FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(self, client, url):
        return fixture_xml

    monkeypatch.setattr(VnExpressSoHoa, "fetch", fake_fetch, raising=True)

    urls = await crawler.list_article_urls(client=None)
    # The 2024-01-01 item must be excluded; recent items kept only if still in window.
    assert all("0000001" not in u for u in urls)
