from src.crawlers.factory import build_crawlers_from_yaml


def test_factory_loads_v2_sources():
    crawlers = build_crawlers_from_yaml()
    names = {c.name for c in crawlers}
    # Spec v2 priority-0 players
    for k in ["momo_newsroom", "grab_vn_blog", "grab_merchant_vn",
              "zalopay_news", "shopee_seller_blog", "telegram_blog"]:
        assert k in names, f"missing {k}"
    # Spec v2 priority-1 media (html + rss)
    for k in ["openai_news", "techcrunch_ai", "vnexpress_kinhdoanh",
              "scmp_tech", "techinasia_fintech", "bloomberg_tech"]:
        assert k in names, f"missing {k}"
    # 36 sources total (25 news + 11 players)
    assert len(crawlers) >= 30


def test_html_crawler_type_built():
    from src.crawlers.html_listing import HtmlListingCrawler

    crawlers = {c.name: c for c in build_crawlers_from_yaml()}
    assert isinstance(crawlers["openai_news"], HtmlListingCrawler)
