from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)


def _make(**overrides) -> RawArticle:
    base = dict(
        id="abc123",
        crawled_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        source="vnexpress_sohoa",
        source_type=SourceType.NEWS,
        url="https://example.com/a",
        title_original="Một tiêu đề",
        content_snippet="snippet",
        published_date=datetime(2026, 5, 5, tzinfo=timezone.utc),
        type=ArticleType.MARKET_PULSE,
        scope=Scope.DOMESTIC,
    )
    base.update(overrides)
    return RawArticle(**base)


def test_make_id_is_deterministic():
    assert RawArticle.make_id("https://x.com/a") == RawArticle.make_id("https://x.com/a")
    assert RawArticle.make_id("https://x.com/a") != RawArticle.make_id("https://x.com/b")


def test_snippet_is_truncated_to_500():
    a = _make(content_snippet="x" * 1000)
    assert len(a.content_snippet) == 500


def test_empty_title_rejected():
    with pytest.raises(ValidationError):
        _make(title_original="   ")


def test_default_status_is_new():
    a = _make()
    assert a.status == Status.NEW


def test_to_row_matches_header_count():
    from src.storage.schema import SHEET_HEADERS

    row = _make().to_row()
    assert len(row) == len(SHEET_HEADERS)
