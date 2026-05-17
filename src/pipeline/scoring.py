"""Basic rough scoring — Market Watch Crawler Instructions v2, Section 3.

signal_score = R1 * 0.6 + R2 * 0.4

This is intentionally a *rough* heuristic — the spec states accurate
scoring is human review. We follow the calibration anchors so the
auto value lands in the right signal-level band most of the time.

Modifiers use the midpoint of each spec range (decided with the user):
  Vietnam            +0.7
  TQ w/ VN precedent +0.4
  US/EU reference    -0.4
Caps:
  rumour/leak             R1 <= 3
  B2B/enterprise          R1 <= 2
  PM promo (periodic)     R1 <= 3.5
  PM launch/pricing/M&A   R1 >= 4
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.storage.models import RawArticle

_NUM_SIGNAL = re.compile(
    r"(\$\s?\d|\d+\s?(triệu|tỷ|tỉ|million|billion|%|USD|user|users|"
    r"người dùng|GMV|đơn|lượt))",
    re.IGNORECASE,
)
_LEAK = re.compile(r"\b(rò rỉ|tin đồn|leak|được cho là|có thể sắp|sắp ra mắt)\b",
                   re.IGNORECASE)
_B2B = re.compile(r"\b(enterprise|B2B|B2G|doanh nghiệp lớn|SDK|API release|"
                  r"on-prem|self-hosted)\b", re.IGNORECASE)
_PROMO = re.compile(r"\b(ưu đãi|khuyến mãi|giảm giá|hoàn tiền|cashback|"
                    r"voucher|mã giảm|flash sale|deal)\b", re.IGNORECASE)
_LAUNCH = re.compile(r"\b(ra mắt|launch|công bố|phát hành|M&A|mua lại|"
                     r"sáp nhập|pricing change|đổi giá|cập nhật phí)\b",
                     re.IGNORECASE)
_REG = re.compile(r"\b(luật|nghị định|thông tư|sắc lệnh|ban hành|"
                  r"regulation|quy định|chính sách)\b", re.IGNORECASE)

SIGNAL_BANDS = [
    (4.21, 5.00, "5 - Industry disruption"),
    (3.41, 4.20, "4 - Strategic shift"),
    (2.51, 3.40, "3 - Market signal"),
    (1.61, 2.50, "2 - Minor signal"),
    (0.00, 1.60, "1 - Noise"),
]


def signal_level_for(score: float) -> str:
    for lo, hi, label in SIGNAL_BANDS:
        if lo <= score <= hi:
            return label
    return "1 - Noise"


@dataclass
class Scores:
    R1: float
    R2: float
    signal_score: float
    signal_level: str


def _haystack(a: RawArticle) -> str:
    return f"{a.title_original or ''} {a.content_snippet or ''}"


def score_article(a: RawArticle) -> Scores:
    hay = _haystack(a)
    topic_group = getattr(a, "_topic_group", "Market Pulse")
    sub_topic = getattr(a, "_sub_topic_group", "Quốc tế")
    review_flag = getattr(a, "_review_flag", False)

    # ---- R1 base (Impact) ----
    r1 = 3.0
    if _REG.search(hay):
        r1 = 4.0
    if _LAUNCH.search(hay):
        r1 = max(r1, 4.0)

    # R1 modifiers (midpoint of spec ranges) — applied BEFORE caps
    if sub_topic == "Trong nước":
        r1 += 0.7
    elif sub_topic == "Trung quốc":
        r1 += 0.4
    elif sub_topic == "Quốc tế":
        r1 -= 0.4

    # R1 caps / floors — applied LAST so nothing overrides them
    is_pm = topic_group == "Players Movement"
    if is_pm and _LAUNCH.search(hay):
        r1 = max(r1, 4.0)                       # PM launch/pricing/M&A floor
    elif is_pm and _PROMO.search(hay):
        r1 = min(r1, 3.5)                       # PM periodic promo cap
    if _LEAK.search(hay):
        r1 = min(r1, 3.0)
    if _B2B.search(hay):
        r1 = min(r1, 2.0)
    r1 = max(1.0, min(5.0, r1))

    # ---- R2 base (Relevance) ----
    r2 = 3.0
    if topic_group == "Players Movement":
        r2 = 4.0
    # concrete signal modifier
    if _NUM_SIGNAL.search(hay):
        r2 += 0.3
    # foreign-context-unfit
    if sub_topic == "Quốc tế" and not _NUM_SIGNAL.search(hay):
        r2 -= 0.3
    # abstract/opinion (very short, no actor numbers)
    if len(hay.split()) < 25 and not _NUM_SIGNAL.search(hay):
        r2 -= 0.3
    r2 = max(1.0, min(5.0, r2))

    signal = round(r1 * 0.6 + r2 * 0.4, 2)
    return Scores(R1=round(r1, 2), R2=round(r2, 2),
                  signal_score=signal, signal_level=signal_level_for(signal))


def apply_scoring(articles: list[RawArticle]) -> None:
    """Stash R1/R2/signal_score/signal_level on each article in place."""
    for a in articles:
        s = score_article(a)
        a._R1 = s.R1                       # type: ignore[attr-defined]
        a._R2 = s.R2                       # type: ignore[attr-defined]
        a._signal_score = s.signal_score   # type: ignore[attr-defined]
        a._signal_level = s.signal_level   # type: ignore[attr-defined]
