from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.utils.date_utils import extract_published, within_window


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def test_og_published_time():
    dt = extract_published(
        _soup('<meta property="og:published_time" '
              'content="2026-05-15T08:00:00+07:00">')
    )
    assert dt is not None and dt.year == 2026 and dt.month == 5 and dt.day == 15


def test_jsonld_date_published():
    dt = extract_published(
        _soup('<script type="application/ld+json">'
              '{"@type":"NewsArticle","datePublished":"2026-05-14"}</script>')
    )
    assert dt is not None and dt.day == 14


def test_time_datetime_attr():
    dt = extract_published(_soup('<time datetime="2026-05-12">12 thg 5</time>'))
    assert dt is not None and dt.day == 12


def test_vietnamese_meta_date():
    dt = extract_published(
        _soup('<meta name="pubdate" content="Thứ Sáu, 16/05/2026">')
    )
    assert dt is not None and dt.day == 16


def test_date_from_url_path():
    dt = extract_published(
        _soup("<html></html>"),
        "https://vnexpress.net/kinh-doanh/2026/05/10/abc.html",
    )
    assert dt is not None and dt.month == 5 and dt.day == 10


def test_no_date_returns_none():
    assert extract_published(_soup("<p>không có ngày tháng</p>")) is None


def test_within_window_rejects_none_and_stale():
    assert within_window(None, 7) is False
    old = datetime.now(timezone.utc) - timedelta(days=30)
    assert within_window(old, 7) is False
    fresh = datetime.now(timezone.utc) - timedelta(days=2)
    assert within_window(fresh, 7) is True
