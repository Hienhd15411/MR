from datetime import datetime, timezone

from src.pipeline.dedup import deduplicate
from src.storage.models import ArticleType, RawArticle, Scope, SourceType


def _art(title, priority=1, snippet="", url=None):
    a = RawArticle(
        id=RawArticle.make_id(url or title),
        crawled_at=datetime.now(timezone.utc),
        source="s", source_type=SourceType.NEWS,
        url=url or f"https://x.test/{abs(hash(title))}",
        title_original=title, content_snippet=snippet,
        published_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        type=ArticleType.MARKET_PULSE, scope=Scope.DOMESTIC,
    )
    a._source_priority = priority
    return a


def test_distinct_titles_not_deduped():
    arts = [
        _art("MoMo ra mắt Ví Trả Sau 2.0 tính năng mới"),
        _art("Indonesia ban hành trần phí ride-hailing 8 phần trăm"),
    ]
    uniq, dups = deduplicate(arts)
    assert len(uniq) == 2
    assert len(dups) == 0


def test_near_duplicate_deduped_keep_higher_priority():
    a = _art("TikTok đầu tư 25 tỷ USD vào Thái Lan mở rộng", priority=2)
    b = _art("TikTok đầu tư 25 tỷ USD vào Thái Lan mở rộng", priority=1,
             url="https://other.test/2")
    uniq, dups = deduplicate([a, b])
    assert len(uniq) == 1
    assert len(dups) == 1
    assert uniq[0]._source_priority == 1  # priority 1 beats 2
    assert dups[0]._discard_reason.startswith("DUPLICATE_OF_")


def test_same_priority_keep_longer_snippet():
    a = _art("Gemini Personal Intelligence ra mắt Việt Nam", priority=1,
             snippet="ngắn")
    b = _art("Gemini Personal Intelligence ra mắt Việt Nam", priority=1,
             snippet="nội dung chi tiết hơn nhiều " * 5,
             url="https://x.test/longer")
    uniq, dups = deduplicate([a, b])
    assert len(uniq) == 1
    assert len(uniq[0].content_snippet) > 50
