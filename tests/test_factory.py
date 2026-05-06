from src.crawlers.factory import build_crawlers_from_yaml
from src.crawlers.rss import RSSCrawler


def test_factory_loads_news_and_players():
    crawlers = build_crawlers_from_yaml()
    names = {c.name for c in crawlers}
    # At least our flagship sources must be wired up.
    assert "vnexpress_sohoa" in names
    assert "techcrunch" in names
    assert "momo_newsroom" in names
    assert "grab_vn_blog" in names
    # 23 = 21 news + 2 players (allow a small margin if YAML evolves).
    assert len(crawlers) >= 20

    rss_news = [c for c in crawlers if isinstance(c, RSSCrawler)]
    assert len(rss_news) >= 18
