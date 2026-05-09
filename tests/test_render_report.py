import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_report import render  # noqa: E402


SAMPLE = [
    {
        "id": "a1", "type": "market_pulse", "scope": "international",
        "url": "https://x.test/a1",
        "week": "W18-26",
        "topic_group": "Market Pulse",
        "sub_topic_group": "Thị trường thế giới",
        "category": "Fintech",
        "subcategory": "Agentic payments",
        "related_vertical": "E-wallet",
        "title_normalized": "Stripe Link ra mắt: ví điện tử cho AI agent",
        "summary": "• What\n• Numbers\n• Implication",
        "start_date": "30/04/2026",
        "end_date": "",
        "signal_level": "4",
        "mentioned_players": "Stripe, OpenAI",
        "ai_processed_at": "2026-05-06T01:00:00+00:00",
    },
    {
        "id": "b2", "type": "players_movement", "scope": "domestic",
        "player": "MoMo",
        "url": "https://x.test/b2",
        "week": "W18-26",
        "topic_group": "Players Movement",
        "sub_topic_group": "MoMo",
        "category": "Marketing",
        "subcategory": "Transaction Growth",
        "related_vertical": "Travel",
        "title_normalized": "MoMo Du lịch × Sale 5.5: Ưu đãi vé máy bay/tàu/khách sạn",
        "summary": "• Thời gian: 24/04 – 05/05\n• Đối tượng: KH MoMo Travel",
        "start_date": "24/04/2026",
        "end_date": "05/05/2026",
        "signal_level": "3",
        "mentioned_players": "MoMo, VietJet",
        "ai_processed_at": "2026-05-06T01:00:00+00:00",
    },
]


def test_render_contains_section_headers():
    md = render(SAMPLE)
    assert "Weekly Market Watch" in md
    assert "1.1 Market Pulse | Thị trường thế giới" in md
    assert "1.2 Market Pulse | Thị trường trong nước" in md
    assert "2.1 Players Movement | MoMo" in md
    assert "2.4 Players Movement | Traveloka" in md  # new player
    assert "2.7 Players Movement | WhatsApp" in md  # new player


def test_render_includes_dates_and_signal():
    md = render(SAMPLE)
    assert "**Thời gian:** 24/04/2026 – 05/05/2026" in md
    assert "**Hiệu lực từ:** 30/04/2026" in md
    assert "signal `4`" in md
    assert "signal `3`" in md


def test_render_includes_mentioned_players():
    md = render(SAMPLE)
    assert "Stripe, OpenAI" in md
    assert "MoMo, VietJet" in md
