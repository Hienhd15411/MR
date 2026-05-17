from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.utils.date_utils import (
    extract_published,
    listing_date_near,
    parse_date,
    scan_date,
    within_window,
)


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


def test_scan_date_formats():
    assert scan_date("Cập nhật ngày 15/05/2026 lúc 9h").day == 15
    assert scan_date("Đăng 15 tháng 5, 2026").month == 5
    assert scan_date("May 12, 2026 by Grab").day == 12
    assert scan_date("15/05").month == 5


def test_scan_date_ignores_promo_amounts():
    assert scan_date("Giảm 30% tối đa 120k đơn từ 500.000đ hoàn 8.686Đ") is None
    assert scan_date("không có ngày tháng") is None


def test_parse_date_is_day_first():
    # Vietnamese convention: 05/06/2026 == 5 June, not 6 May.
    dt = parse_date("05/06/2026")
    assert dt is not None and dt.day == 5 and dt.month == 6


def test_parse_date_iso_not_swapped():
    dt = parse_date("2026-05-12")
    assert dt is not None and dt.month == 5 and dt.day == 12


def test_listing_date_near_span_and_time():
    a = BeautifulSoup(
        '<div><a href="/p/x">Ưu đãi</a>'
        '<span class="post-date">17/05/2026</span></div>',
        "html.parser",
    ).find("a")
    dt = listing_date_near(a)
    assert dt is not None and dt.day == 17

    a2 = BeautifulSoup(
        '<li><a href="/p/y">Tin</a>'
        '<time datetime="2026-05-14">14 thg 5</time></li>',
        "html.parser",
    ).find("a")
    assert listing_date_near(a2).day == 14

    a3 = BeautifulSoup(
        '<div><a href="/p/z">Không ngày</a></div>', "html.parser"
    ).find("a")
    assert listing_date_near(a3) is None


def test_within_window_rejects_none_and_stale():
    assert within_window(None, 7) is False
    old = datetime.now(timezone.utc) - timedelta(days=30)
    assert within_window(old, 7) is False
    fresh = datetime.now(timezone.utc) - timedelta(days=2)
    assert within_window(fresh, 7) is True
