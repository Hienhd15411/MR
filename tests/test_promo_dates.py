from src.utils.promo_dates import extract_promo_dates


def test_range_full():
    s, e = extract_promo_dates("Chương trình từ ngày 24/04 đến 05/05/2026 áp dụng")
    assert s == "24/04/2026"
    assert e == "05/05/2026"


def test_range_dash():
    s, e = extract_promo_dates("Ưu đãi 24/4 - 5/5/2026 cho khách mới")
    assert s == "24/04/2026"
    assert e == "05/05/2026"


def test_start_only():
    s, e = extract_promo_dates("Áp dụng từ 01/03/2026 trên toàn hệ thống")
    assert s == "01/03/2026"
    assert e == ""


def test_end_only():
    s, e = extract_promo_dates("Khuyến mãi kéo dài đến hết 31/5/2026")
    assert e == "31/05/2026"


def test_no_dates():
    s, e = extract_promo_dates("Tin tức không có ngày tháng cụ thể nào")
    assert s == "" and e == ""
