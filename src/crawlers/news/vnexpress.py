from __future__ import annotations

from src.crawlers.rss import RSSCrawler


class VnExpressSoHoa(RSSCrawler):
    def __init__(self) -> None:
        super().__init__(
            name="vnexpress_sohoa",
            rss_url="https://vnexpress.net/rss/so-hoa.rss",
            scope="domestic",
            type_="market_pulse",
            source_type="news",
            detail_selector="h1.title-detail",
        )
