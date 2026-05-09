from datetime import datetime, timezone

from src.pipeline.filter import CategoryClassifier, apply_filter
from src.storage.models import (
    ArticleType,
    RawArticle,
    Scope,
    SourceType,
    Status,
)


def _art(title: str, snippet: str = "", t: ArticleType = ArticleType.MARKET_PULSE,
         scope: Scope = Scope.DOMESTIC) -> RawArticle:
    return RawArticle(
        id=RawArticle.make_id(title),
        crawled_at=datetime.now(timezone.utc),
        source="test",
        source_type=SourceType.NEWS,
        url=f"https://x.test/{abs(hash(title))}",
        title_original=title,
        content_snippet=snippet,
        published_date=datetime.now(timezone.utc),
        type=t,
        scope=scope,
    )


def test_classifies_ai_with_subcategory():
    a = _art("OpenAI ra mắt GPT-5 với khả năng agentic mạnh mẽ")
    CategoryClassifier().classify(a)
    assert a.pre_category is not None
    assert a.pre_category.startswith("AI")
    assert "AI agents" in a.pre_category
    assert a.status == Status.NEW


def test_classifies_fintech():
    a = _art("Ngân hàng số ra mắt ví điện tử mới cho người dùng Việt Nam")
    CategoryClassifier().classify(a)
    assert a.pre_category == "Fintech/E-wallet"


def test_player_match_overrides_to_players_movement():
    a = _art("MoMo hợp tác với một ngân hàng để mở rộng dịch vụ thanh toán")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.PLAYERS_MOVEMENT
    assert a.player == "MoMo"
    assert a.pre_category is not None
    assert "Partnership" in a.pre_category


def test_grab_marketing_subcategory():
    a = _art("Grab tung chiến dịch khuyến mãi để thu hút người dùng mới")
    CategoryClassifier().classify(a)
    assert a.player == "Grab"
    assert a.pre_category is not None
    assert a.pre_category.startswith("Marketing")


def test_no_match_marks_filtered_out():
    a = _art("Thời tiết Hà Nội cuối tuần này có mưa rào")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT
    assert a.pre_category is None


def test_word_boundary_does_not_match_substring():
    # "AI" must not match inside "AirAsia"
    a = _art("AirAsia thông báo mở thêm đường bay tới Đà Nẵng")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_acronym_ai_does_not_match_vietnamese_pronoun():
    # "ai" in Vietnamese is a pronoun ("who/anyone"). Must not trigger AI.
    a = _art("Ai cũng có thể đăng ký gói cước mới của nhà mạng")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_acronym_ai_still_matches_uppercase():
    a = _art("AI tạo sinh đang thay đổi mọi ngành công nghiệp")
    CategoryClassifier().classify(a)
    assert a.pre_category is not None
    assert a.pre_category.startswith("AI")


def test_chatgpt_classifies_as_big_tech_ai():
    a = _art("ChatGPT vừa cập nhật phiên bản mới với khả năng vượt trội")
    CategoryClassifier().classify(a)
    assert a.pre_category == "AI/Big tech AI"


def test_techcombank_classifies_as_fintech():
    a = _art("Techcombank ra mắt dịch vụ chuyển khoản quốc tế mới")
    CategoryClassifier().classify(a)
    assert a.pre_category == "Fintech/E-wallet"


def test_ghn_classifies_as_tmdt():
    a = _art("GHN mở rộng mạng lưới giao hàng tại miền Trung")
    CategoryClassifier().classify(a)
    assert a.pre_category == "TMĐT"


def test_vietjet_classifies_as_travel():
    a = _art("VietJet công bố đường bay mới tới Hàn Quốc")
    CategoryClassifier().classify(a)
    assert a.pre_category == "Travel/Khách sạn/Giải trí"


def test_adjacent_player_only_classifies_as_market_pulse():
    # Stripe is adjacent (not tracked). Article kept as Market Pulse, not PM.
    a = _art("Stripe ra mắt Link – ví điện tử cho AI agent")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.MARKET_PULSE
    # Stripe also matches Fintech keywords → category set
    assert a.pre_category is not None
    assert a.player is None  # adjacent player doesn't fill `player`


def test_tracked_player_traveloka_classifies_as_pm():
    a = _art("Traveloka ra mắt sản phẩm mới cho mảng đặt phòng quốc tế")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.PLAYERS_MOVEMENT
    assert a.player == "Traveloka"


def test_tracked_player_whatsapp_classifies_as_pm():
    a = _art("WhatsApp triển khai nạp tiền trả trước tại Ấn Độ, hợp tác PayU")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.PLAYERS_MOVEMENT
    assert a.player == "WhatsApp"


def test_apply_filter_returns_all_with_counts():
    arts = [
        _art("OpenAI giới thiệu GPT-5"),
        _art("Tin thời tiết bình thường"),
    ]
    out = apply_filter(arts)
    assert len(out) == 2
    statuses = [a.status for a in out]
    assert Status.NEW in statuses and Status.FILTERED_OUT in statuses
