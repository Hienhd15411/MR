from datetime import datetime, timezone

from src.pipeline.scoring import score_article, signal_level_for
from src.storage.models import ArticleType, RawArticle, Scope, SourceType


def _art(title, snippet="", topic="Market Pulse", sub="Quốc tế"):
    a = RawArticle(
        id="x", crawled_at=datetime.now(timezone.utc), source="s",
        source_type=SourceType.NEWS, url="https://x", title_original=title,
        content_snippet=snippet, published_date=datetime.now(timezone.utc),
        type=ArticleType.MARKET_PULSE, scope=Scope.DOMESTIC,
    )
    a._topic_group = topic
    a._sub_topic_group = sub
    return a


def test_signal_level_bands():
    assert signal_level_for(5.0) == "5 - Industry disruption"
    assert signal_level_for(4.21) == "5 - Industry disruption"
    assert signal_level_for(3.8) == "4 - Strategic shift"
    assert signal_level_for(3.0) == "3 - Market signal"
    assert signal_level_for(2.0) == "2 - Minor signal"
    assert signal_level_for(1.0) == "1 - Noise"


def test_formula_is_r1_60_r2_40():
    s = score_article(_art("Một tin thị trường bình thường về fintech"))
    assert abs(s.signal_score - round(s.R1 * 0.6 + s.R2 * 0.4, 2)) < 0.01


def test_vietnam_modifier_boosts_r1():
    intl = score_article(_art("Quy định mới ban hành", sub="Quốc tế"))
    vn = score_article(_art("Quy định mới ban hành", sub="Trong nước"))
    assert vn.R1 > intl.R1


def test_b2b_caps_r1():
    s = score_article(_art("OpenAI ra mắt enterprise SDK B2B cho doanh nghiệp lớn",
                           sub="Quốc tế"))
    assert s.R1 <= 2.0


def test_leak_caps_r1():
    s = score_article(_art("Tin đồn Anthropic sắp ra mắt công cụ thiết kế",
                           sub="Trong nước"))
    assert s.R1 <= 3.0


def test_pm_promo_capped():
    a = _art("Grab tung ưu đãi hoàn tiền giảm giá cuối tuần",
             topic="Players Movement", sub="Trong nước")
    s = score_article(a)
    assert s.R1 <= 3.5
