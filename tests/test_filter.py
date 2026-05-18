from datetime import datetime, timezone

from src.pipeline.filter import TierFilter, apply_filter
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)


def _art(title, snippet="", player=None, type_=ArticleType.MARKET_PULSE):
    return RawArticle(
        id=RawArticle.make_id(title),
        crawled_at=datetime.now(timezone.utc),
        source="x",
        source_type=SourceType.NEWS,
        url=f"https://x.test/{abs(hash(title))}",
        title_original=title,
        content_snippet=snippet,
        published_date=datetime.now(timezone.utc),
        type=type_,
        player=player,
        scope=Scope.DOMESTIC,
    )


def _clf():
    return TierFilter()


def test_priority0_player_always_kept():
    f = _clf()
    a = _art("Bất kỳ tiêu đề khuyến mãi gì đó", player="MoMo")
    v = f.classify(a, "momo_newsroom")  # priority 0 in sources.yaml
    assert v.keep
    assert v.topic_group == "Players Movement"


def test_tier1_keyword_kept():
    f = _clf()
    a = _art("OpenAI ra mắt GPT-5 với khả năng agentic mới")
    v = f.classify(a, "techcrunch_ai")
    assert v.keep
    assert v.discard_reason == ""


def test_tier3_only_discarded():
    f = _clf()
    a = _art("Top 10 địa điểm du lịch hè must-visit, cẩm nang du lịch chi tiết")
    v = f.classify(a, "vnexpress_khcn")
    assert not v.keep
    assert v.discard_reason == "T3_TRAVEL_TIPS"


def test_tier3_exception_rescues():
    f = _clf()
    # travel tips BUT mentions Traveloka platform → exception → not T3
    a = _art("Cẩm nang du lịch hè: đặt phòng qua Traveloka tiết kiệm")
    v = f.classify(a, "vnexpress_kinhdoanh")
    assert v.keep  # rescued by exception, then Tier-1 (Traveloka) keeps it


def test_tier1_plus_tier3_human_review():
    f = _clf()
    # Has Tier-1 (ChatGPT) AND Tier-3 (review phim) → Tier-4 flag
    a = _art("ChatGPT viết kịch bản review phim bom tấn mùa hè")
    v = f.classify(a, "genk_ai")
    assert v.keep
    assert v.review_flag


def test_no_keyword_discarded():
    f = _clf()
    a = _art("Thời tiết Hà Nội cuối tuần có mưa rào vài nơi")
    v = f.classify(a, "vnexpress_khcn")
    assert not v.keep
    assert v.discard_reason == "NO_KEYWORD"


def test_geography_vn():
    f = _clf()
    a = _art("MoMo hợp tác ngân hàng tại Việt Nam mở rộng thanh toán QR")
    v = f.classify(a, "vnexpress_kinhdoanh")
    assert v.sub_topic_group == "Trong nước"


def test_geography_sea_priority_over_tq():
    f = _clf()
    a = _art("Shopee Trung Quốc đầu tư mở rộng marketplace tại Indonesia")
    v = f.classify(a, "techinasia_ecom")
    assert v.keep
    assert v.sub_topic_group == "SEA"


def test_tier3_priority3_source_short_is_human_review():
    f = _clf()
    # priority-3 source + no t1/t3 + has 1 tier-2 (Apple) → t4 trigger
    a = _art("Apple công bố vài thông tin", "ngắn")
    v = f.classify(a, "genk_ict")
    assert v.keep
    assert v.review_flag


def test_apply_filter_splits_kept_discarded():
    arts = [
        (_art("OpenAI ra mắt GPT-5 agentic"), "techcrunch_ai"),
        (_art("Top 10 resort sang chảnh phải đi hè này"), "vnexpress_khcn"),
    ]
    kept, discarded = apply_filter(arts)
    assert len(kept) == 1
    assert len(discarded) == 1
    assert kept[0].status == Status.NEW
    assert discarded[0].status == Status.FILTERED_OUT


# ---------------------------------------------------------------------------
# Round-1 hard-exclude (categories.yaml exclude_patterns) — previously dead
# config, now wired into TierFilter. Each of these editorial-noise headlines
# must be DISCARDed regardless of theme score.
# ---------------------------------------------------------------------------

import pytest

_NOISE = [
    "Marketing operating system Nectar Social raises $30M Series A led by Menlo",
    "Power prices are up 76% on America’s biggest grid, watchdog points fingers",
    "Shein said to buy Everlane from L Catterton for $100m",
    "Sony A7R VI ra mắt: máy ảnh không gương lật giá 114 triệu",
    "Clip tai nạn bếp gas khiến cả nhà hoảng loạn",
    "Dùng câu lệnh AI xóa vật thể trên ảnh chỉ trong vài giây",
    "Điện thoại Trump T1 bắt đầu được giao hàng",
    "LG ra mắt loạt TV 2026 với kích thước lớn",
    "Thu giữ loạt hàng giả ở Saigon Square, chợ Bến Thành",
    "HK biotech firm uses AI to produce nano rockets for drug discovery",
    "Kuaishou shares soar as Kling AI eyes US$20 billion valuation in spin-off",
    "Chip capacity crunch crisis deepens across foundries",
    "Chinese chip pioneer hypes 2nm breakthrough",
    "China’s CXMT sees H1 revenue rise pre-IPO",
    "Trải nghiệm Spot+Scrub AI - robot lau nhà đầu tiên của Dyson",
    "Altman bị tố nói dối, Musk bị chê 'mất trí nhớ chọn lọc'",
]


@pytest.mark.parametrize("title", _NOISE)
def test_exclude_patterns_discard_noise(title):
    f = _clf()
    v = f.classify(_art(title), "techinasia_feed")  # non-player news source
    assert not v.keep, f"should be excluded: {title}"
    assert v.discard_reason.startswith("EXCLUDE_"), v.discard_reason


def test_exclude_exempts_priority0_player_blog():
    # A player-blog post that happens to contain an exclude keyword
    # ("máy ảnh") must still be kept — player sources bypass exclude.
    f = _clf()
    a = _art("MoMo tặng ưu đãi khi mua máy ảnh trả góp", player="MoMo")
    v = f.classify(a, "momo_newsroom")
    assert v.keep
    assert v.topic_group == "Players Movement"


def test_exclude_does_not_kill_legit_vn_tech():
    # "khởi công" accent-free alias used to false-match "Khối Công nghệ".
    f = _clf()
    a = _art("CMC tái cấu trúc Khối Công nghệ và Giải pháp, thúc đẩy chuyển đổi AI")
    v = f.classify(a, "vneconomy_techconnect")
    assert v.keep
    assert not v.discard_reason.startswith("EXCLUDE_")
