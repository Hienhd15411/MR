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
