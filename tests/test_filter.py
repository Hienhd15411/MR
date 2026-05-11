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
    # Must include a business signal (here: "ra mắt") to pass the executive gate.
    a = _art("AI tạo sinh ra mắt phiên bản mới mạnh hơn cho doanh nghiệp")
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


def test_ghn_in_app_logistics_partnership_classifies():
    # GHN tích hợp với marketplace là super-app concern.
    # (Avoid mentioning a tracked player so this stays Market Pulse.)
    a = _art(
        "GHN ra mắt API tích hợp giao hàng trực tiếp cho các sàn "
        "thương mại điện tử lớn"
    )
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert a.pre_category == "TMĐT"


def test_vietjet_super_app_partnership_classifies():
    # Strategic super-app angle, not just route announcement
    a = _art(
        "VietJet công bố hợp tác chiến lược với Grab tích hợp đặt vé "
        "máy bay trong super-app"
    )
    CategoryClassifier().classify(a)
    assert a.pre_category is not None


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


# --- Business-signal gate (executive-grade filter) ----------------------


def test_netflix_business_move_is_kept():
    # Brand + business action — keep
    a = _art("Netflix ra mắt gói cước có quảng cáo tại thị trường Việt Nam")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert a.pre_category is not None


def test_player_news_always_kept():
    # Tracked player → always keep (Round 1 is permissive). Any noise
    # clearance happens at Round 2 (AI manual).
    a = _art("MoMo công bố hợp tác chiến lược với BIDV mở rộng QR xuyên biên giới")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert a.player == "MoMo"


def test_player_promo_kept_player_blogs_are_in_scope():
    # MoMo lì xì promo titles ARE in anh's Database (kept by Round 1).
    a = _art("Lắc Xì MoMo: Lấy 10 miếng vàng 0,1 chỉ, 2 iPad Mini, quà sức khỏe từ Chubb")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert a.player == "MoMo"


def test_adjacent_player_with_business_action_kept():
    a = _art("Stripe ra mắt Link – ví điện tử cho AI agent tự động thanh toán")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.MARKET_PULSE
    assert a.status == Status.NEW


# --- V-app editorial relevance scoring ---------------------------------


def test_relevance_score_attached():
    a = _art("MoMo công bố hợp tác chiến lược với BIDV mở rộng QR xuyên biên giới")
    CategoryClassifier().classify(a)
    score = getattr(a, "_relevance_score", 0)
    # tracked player (5) + payment_wallet_war theme (5) + signal (1) = 11+
    assert score >= 10
    assert "payment_wallet_war" in (getattr(a, "_matched_themes", "") or "")


def test_galaxy_with_ai_features_kept():
    # Anh keeps these in Database. Gadget brand + AI angle → KEEP via AI vertical.
    a = _art("Galaxy S26 series có 7 tính năng AI mới: Tự mở app gọi xe, đặt đồ ăn, chỉnh ảnh bằng giọng nói")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_in_scope_vertical_alone_is_now_kept():
    # Round 1 is permissive — vertical match alone passes. Round 2 will curate.
    a = _art("Lazada tung khuyến mãi giảm 50% nhân ngày của mẹ")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


# --- PM bug fixes -----------------------------------------------------


def test_player_in_body_not_title_stays_market_pulse():
    # Indonesia regulation article mentions Grab in body but is MP, not PM
    a = _art(
        "App gọi xe trước sức ép giảm chiết khấu",
        snippet=("Tổng thống Indonesia Prabowo Subianto đã ký quy định mới, "
                 "yêu cầu các nền tảng như Grab và GoTo giảm mức phí từ 20% xuống 8%."),
    )
    CategoryClassifier().classify(a)
    # Kept (Grab mentioned + Ride/Food vertical)
    assert a.status == Status.NEW
    # But classified as MP since Grab not in title
    assert a.type == ArticleType.MARKET_PULSE
    assert a.player is None


def test_player_in_title_classifies_as_pm():
    a = _art("Grab cập nhật phí nền tảng và phí dịch vụ từ 28/04")
    CategoryClassifier().classify(a)
    assert a.type == ArticleType.PLAYERS_MOVEMENT
    assert a.player == "Grab"


def test_ban_keyword_no_longer_matches_BAN_in_BAN_DO():
    # BẢN ĐỒ stripped to BAN DO must NOT match Regulation "ban" keyword
    # (which has been removed). The signal_type should be Marketing, not
    # Regulation, for promo titles like this.
    a = _art("THAM GIA THỬ THÁCH BẢN ĐỒ BUNG SỨC MÙA THI CÙNG GRAB SINH VIÊN")
    clf = CategoryClassifier()
    clf.classify(a)
    sig = getattr(a, "_business_signal", "") or ""
    assert sig != "Regulation", f"unexpected Regulation signal: {sig}"


def test_security_incident_kept():
    # Anh's Database keeps platform security incidents — they're
    # legitimately relevant to player risk monitoring.
    a = _art("Tái diễn chiêu trò lừa đảo chiếm đoạt tài khoản Telegram tại Việt Nam")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_platform_regulation_passes_high_score():
    a = _art(
        "Indonesia ban hành sắc lệnh cắt phí nền tảng ride-hailing xuống 8% — "
        "ảnh hưởng Grab và GoTo"
    )
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    score = getattr(a, "_relevance_score", 0)
    # platform_regulation (5) + mobility theme (4) + tracked Grab (5) + signal (1)
    assert score >= 10


# --- Noise / clickbait drops -------------------------------------------


def test_question_title_now_kept_for_market_analysis():
    # Anh's Database keeps "Vì sao …", "Có gì ở …" market-analysis
    # explainers. Question pattern was removed from Round 1 noise.
    a = _art("Vì sao doanh nghiệp Việt thất bại khi ứng dụng AI?")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_personality_opinion_now_kept():
    # Removed personality opinion noise — anh keeps "Mark Cuban cảnh báo"
    # type pieces (they often have follow-up substance).
    a = _art("Mark Cuban cảnh báo \"lỗ hổng chí mạng\" của AI")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_bitcoin_ticker_dropped():
    a = _art("Giá Bitcoin hôm nay 9.5.2026: Lấy lại mốc 80.000 USD")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_gadget_rumour_dropped():
    a = _art("iPhone 18 Pro lộ nâng cấp màn hình đắt giá")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_clickbait_health_dropped():
    a = _art("Dùng AI quá 10 phút/ngày? Bạn đang tự hủy hoại bộ não mình")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_listicle_dropped():
    a = _art("Top 5 ứng dụng AI giúp bạn làm việc hiệu quả hơn")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


# --- Off-domain (heavy industry / gadget / promo spam) ----------------


def test_heavy_industry_steel_dropped():
    a = _art("Bắt tay 'gã khổng lồ' Nhật làm thép, tỷ phú Phạm Nhật Vượng chọn đối tác tỷ đô")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_real_estate_megaproject_dropped():
    a = _art("Vinhomes của tỷ phú Phạm Nhật Vượng sẽ khởi công siêu dự án 23.600 tỷ đồng")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_railway_infrastructure_dropped():
    a = _art("Pháp muốn tham gia siêu dự án đường sắt tốc độ cao Bắc - Nam")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_smartphone_release_dropped():
    a = _art("OPPO Find X9 Ultra và Find X9s ra mắt tại Việt Nam, giá từ 25 triệu đồng")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_motorbike_release_dropped():
    a = _art("Suzuki tung ra mẫu xe côn tay chỉ hơn 30 triệu đồng")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_all_caps_promo_kept_for_tracked_player():
    # Tracked player promo banners — anh's Database keeps them (Round 2
    # AI will normalise the title). Round 1 keeps player content as-is.
    a = _art("GRABUNLIMITED – MỞ GRAB LUÔN CÓ MÃ ÁP")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert a.player == "Grab"


def test_emoji_prefix_kept_for_tracked_player():
    a = _art("🚀 THAM GIA THỬ THÁCH CÙNG GRAB SINH VIÊN 🎁")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_all_caps_non_player_dropped():
    # All-caps without tracked player — still drops as noise.
    a = _art("CƠN SỐT KHUYẾN MÃI: GIẢM 50% TẠI MỌI CỬA HÀNG")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_too_short_dropped():
    a = _art("Khuyến mãi")
    CategoryClassifier().classify(a)
    assert a.status == Status.FILTERED_OUT


def test_vinpearl_partnership_kept():
    # Real travel-strategic news must pass
    a = _art("Vinpearl hợp tác với 3 doanh nghiệp lữ hành hàng đầu Ấn Độ khai mở thị trường 1,47 tỷ dân")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW


def test_concrete_funding_round_kept():
    a = _art("Anthropic gọi vốn vòng mới với định giá gần 1 nghìn tỷ USD")
    CategoryClassifier().classify(a)
    assert a.status == Status.NEW
    assert getattr(a, "_relevance_score", 0) >= 5


def test_articles_sorted_by_relevance():
    arts = [
        _art("VietJet công bố đường bay mới — không liên quan thị trường super-app"),
        _art("MoMo ra mắt agentic payment hợp tác Stripe và Anthropic"),
    ]
    out = apply_filter(arts)
    # The MoMo article should be ranked higher (or at least kept above
    # the airline expansion which scores zero / is filtered).
    if len(out) >= 2 and out[0].status == Status.NEW and out[1].status == Status.NEW:
        s0 = getattr(out[0], "_relevance_score", 0)
        s1 = getattr(out[1], "_relevance_score", 0)
        assert s0 >= s1


def test_apply_filter_returns_all_with_counts():
    arts = [
        _art("OpenAI giới thiệu GPT-5"),
        _art("Tin thời tiết bình thường"),
    ]
    out = apply_filter(arts)
    assert len(out) == 2
    statuses = [a.status for a in out]
    assert Status.NEW in statuses and Status.FILTERED_OUT in statuses
