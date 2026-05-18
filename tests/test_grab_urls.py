from src.crawlers.players.grab import LIST_URLS, _looks_like_post


def test_category_pages_are_not_posts():
    for u in [
        "https://www.grab.com/vn/blog/",
        "https://www.grab.com/vn/blog/driver/",
        "https://www.grab.com/vn/blog/merchant/",
        "https://www.grab.com/vn/blog/news",
    ]:
        assert _looks_like_post(u) is False


def test_real_posts_detected():
    assert _looks_like_post(
        "https://www.grab.com/vn/blog/grab-uu-dai-thang-5-2026/"
    )
    assert _looks_like_post("/vn/blog/driver/grab-tang-thuong-tai-xe-quy-2")


def test_section_pages_are_crawled():
    # The driver section the user pointed at must be in the listing set.
    assert "https://www.grab.com/vn/blog/driver/" in LIST_URLS
    assert "https://www.grab.com/vn/blog/" in LIST_URLS
