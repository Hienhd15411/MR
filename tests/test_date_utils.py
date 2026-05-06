from datetime import datetime, timedelta, timezone

from src.utils.date_utils import parse_date, parse_vn_date, within_window


def test_parse_rfc822_pubdate():
    dt = parse_date("Mon, 05 May 2026 03:00:00 +0700")
    assert dt is not None
    assert dt.tzinfo is not None
    # 03:00 +07 -> 20:00 UTC previous day
    assert dt.hour == 20 and dt.day == 4


def test_parse_vn_freeform():
    dt = parse_vn_date("Thứ Hai, 6/5/2026, 14:30 (GMT+7)")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 6


def test_parse_returns_none_on_garbage():
    assert parse_date("not a date string") is None
    assert parse_date("") is None


def test_within_window():
    now = datetime.now(timezone.utc)
    assert within_window(now - timedelta(days=3), days=7)
    assert not within_window(now - timedelta(days=30), days=7)
    assert not within_window(None, days=7)
