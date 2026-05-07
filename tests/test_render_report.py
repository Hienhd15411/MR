import json
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
        "title_original": "Stripe Link launch",
        "title_normalized": "Stripe Link ra mắt: ví điện tử cho AI agent",
        "summary": "• What\n• Numbers\n• Implication",
        "category": "Fintech/E-wallet", "sub_category": "",
        "topic_lens": "Technology", "topic_sub": "Fintech",
        "campaign_period": "",
        "impact_score": 4, "relevance_score": 5, "final_score": 4.4,
        "tags": "stripe", "ai_processed_at": "2026-05-06T01:00:00+00:00",
    },
    {
        "id": "b2", "type": "players_movement", "scope": "domestic",
        "player": "MoMo",
        "url": "https://x.test/b2",
        "title_original": "MoMo travel",
        "title_normalized": "MoMo Du lịch × Sale 5.5: Ưu đãi vé máy bay/tàu/khách sạn",
        "summary": "• Thời gian: 24/04 – 05/05\n• Đối tượng: KH MoMo Travel\n• Ưu đãi: ...",
        "category": "Marketing", "sub_category": "Transaction Growth",
        "topic_lens": "Technology", "topic_sub": "Marketing | Transaction growth",
        "campaign_period": "24/04 – 05/05",
        "impact_score": 3, "relevance_score": 5, "final_score": 3.8,
        "tags": "momo,travel", "ai_processed_at": "2026-05-06T01:00:00+00:00",
    },
]


def test_render_contains_section_headers():
    md = render(SAMPLE)
    assert "Weekly Market Watch" in md
    assert "Bản tin theo ngành" in md
    assert "1.1 Market Pulse | Thị trường thế giới" in md
    assert "1.2 Market Pulse | Thị trường trong nước" in md
    assert "2.1 Players Movement | MoMo" in md
    assert "2.2 Players Movement | Zalo" in md  # empty section
    assert "2.3 Players Movement | Grab" in md
    assert "2.4 Players Movement | Shopee" in md
    assert "2.5 Players Movement | TikTokShop" in md


def test_render_includes_topic_tag_and_period():
    md = render(SAMPLE)
    assert "Technology | Fintech" in md
    assert "Marketing | Transaction growth" in md
    assert "**Thời gian:** 24/04 – 05/05" in md


def test_render_handles_missing_summary_lines():
    rows = [dict(SAMPLE[0], summary="")]
    md = render(rows)
    assert "Stripe Link" in md
