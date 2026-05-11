"""Round 1 (Scanning) filter — matches anh's Excel `Scanning` sheet rule.

Rule:
    KEEP if  (tracked_player OR adjacent_player OR vertical_match)
             AND NOT (exclude_pattern OR noise_title)
    DROP otherwise

Themes / business signals / relevance score are still computed and stashed
on the article as METADATA for the AI Round 2 step. They are NOT gates —
Round 1 deliberately over-includes so Round 2 (AI manual via Claude Code)
has a candidate pool of ~300-500 articles to curate down to ~30-50 that
make the report.

Reference: references/MR26001_MarketWatch_Database.xlsx → sheet
`Scanning` (Bước 1, Round 1) and `Database` (480 rows produced by it).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from loguru import logger

from src.storage.models import ArticleType, RawArticle, Status

CATEGORIES_YAML = Path(__file__).resolve().parents[1] / "config" / "categories.yaml"

# Source name → player mapping. Articles from these player-blog sources
# are auto-tagged as that player even when the title doesn't mention the
# brand (player promo titles like "5.5 Sale" or "Happy Friday" come
# from grab_vn_blog / momo_newsroom / zalopay_news and obviously belong
# to that player).
_SOURCE_TO_PLAYER = {
    "momo_newsroom": "MoMo",
    "grab_vn_blog": "Grab",
    "grab_merchant_vn": "Grab",
    "zalopay_news": "Zalo",
    "zalopay_promo": "Zalo",
    "zalo_oa_news": "Zalo",
    "whatsapp_blog": "WhatsApp",
    "telegram_blog": "Telegram",
    "shopee_seller_blog": "Shopee",
    "tiktokshop_seller_blog": "TikTokShop",
}


def _player_for_source(source: str) -> str | None:
    return _SOURCE_TO_PLAYER.get(source)


# Bonuses kept for downstream sort + Round 2 prioritisation.
_TRACKED_PLAYER_BONUS = 5
_ADJACENT_PLAYER_BONUS = 1
_BUSINESS_SIGNAL_BONUS = 1

# Title-level noise patterns. If the article title matches any of these,
# we drop it regardless of theme/player score — these are clickbait,
# opinion, explainer, lifestyle, ticker or rumour articles that aren't
# strategic intel even when they mention a tracked brand.
_NOISE_TITLE_PATTERNS = [
    # NOTE: question titles are NOT dropped anymore — anh's Database
    # keeps many "Vì sao DN X thất bại?", "Có gì ở mô hình AI Y?" because
    # they are market-analysis explainers. Round 2 AI will filter.
    # Lifestyle / health clickbait — keep only specific shape patterns.
    re.compile(r"^\s*(bí quyết|mẹo|tips)\b", re.IGNORECASE),
    re.compile(r"^\s*cách\s+(làm|sử dụng|đăng ký|nhận|kích hoạt|tải|kiếm tiền)\b",
               re.IGNORECASE),
    re.compile(r"\b(hủy hoại|đe doạ).+(bộ não|sức khỏe|sức khoẻ)\b",
               re.IGNORECASE),
    # Price tickers (commodity, not strategic)
    re.compile(r"\bgiá\s+(bitcoin|btc|eth|vàng|usd|xăng|dầu)\b", re.IGNORECASE),
    re.compile(r"\b(tỷ giá|tỉ giá)\b", re.IGNORECASE),
    re.compile(r"\bbitcoin hôm nay\b", re.IGNORECASE),
    # Rumours / leaks (gadget speculation)
    re.compile(r"\b(rò rỉ|lộ\s+(diện|thông tin|thiết kế|cấu hình|tính năng)|"
               r"sắp\s+(khai tử|ngừng))\b", re.IGNORECASE),
    # Pure gadget reviews / preview titles — narrow scope only
    re.compile(r"^\s*(đánh giá|review|trên tay|hands-on)\s+"
               r"(iphone|samsung|galaxy|macbook|laptop|tablet|smartphone|"
               r"điện thoại|máy tính|tai nghe|đồng hồ|smartwatch)",
               re.IGNORECASE),
    re.compile(r"\b(unboxing|so sánh chi tiết)\b", re.IGNORECASE),
    # Listicle markers
    re.compile(r"^\s*(top\s+\d+|\d+\s+(điều|cách|lý do|bí mật|mẹo))",
               re.IGNORECASE),
    # Title starts with emoji
    re.compile(r"^\s*[\U0001F300-\U0001FAFF☀-➿]+"),
    # Vague single-word nav titles
    re.compile(r"^\s*(thông báo|thông cáo|sự kiện|cộng đồng|khuyến mãi|"
               r"thư viện|ưu đãi)\s*$", re.IGNORECASE),
    # Gadget release with price tag in title (consumer launch)
    re.compile(r"\bgiá\s+(từ\s+)?\d+([\.,]\d+)?\s*(triệu|tr|nghìn|usd|\$)",
               re.IGNORECASE),
    # Vehicle / motorbike releases
    re.compile(r"\bxe\s+(côn\s+tay|máy\s+điện|tay\s+ga)\b", re.IGNORECASE),
]


def _is_noise_title(title: str) -> bool:
    if not title:
        return True  # empty title = drop
    # Drop if too short / no real content
    if len(title.strip()) < 10:
        return True
    # Drop if more than 70% uppercase letters (banner / promo all-caps)
    letters = [c for c in title if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.7 and len(letters) > 6:
            return True
    for pat in _NOISE_TITLE_PATTERNS:
        if pat.search(title):
            return True
    return False


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _is_acronym(keyword: str) -> bool:
    kw = keyword.strip()
    if not kw or " " in kw or len(kw) > 8 or not kw.isascii():
        return False
    return kw.isupper() and any(c.isalpha() for c in kw)


def _build_pattern(keyword: str, case_sensitive: bool = False) -> re.Pattern[str]:
    kw = keyword.strip()
    flags = re.UNICODE
    if not case_sensitive:
        flags |= re.IGNORECASE
    escaped = re.escape(kw)
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", flags)


@dataclass
class CategoryHit:
    category: str
    subcategory: str | None = None
    keyword: str = ""


@dataclass
class _CompiledCategory:
    name: str
    weight: int
    patterns: list[tuple[re.Pattern[str], str]]
    subcategories: list[tuple[str, list[tuple[re.Pattern[str], str]]]]


def _compile_keyword_block(block: dict) -> list[tuple[re.Pattern[str], str]]:
    out: list[tuple[re.Pattern[str], str]] = []
    for kw in block.get("keywords", []) or []:
        cs = _is_acronym(kw)
        out.append((_build_pattern(kw, case_sensitive=cs), kw))
        accent_free = _strip_accents(kw)
        if accent_free != kw and len(accent_free) >= 6 and " " in accent_free.strip():
            out.append((_build_pattern(accent_free, case_sensitive=False), kw))
    return out


def _compile_categories(raw: dict) -> dict[str, list[_CompiledCategory]]:
    sections: dict[str, list[_CompiledCategory]] = {}
    for section, cats in raw.items():
        if not isinstance(cats, dict):
            continue
        compiled: list[_CompiledCategory] = []
        for name, body in cats.items():
            body = body or {}
            weight = int(body.get("weight", 1))
            patterns = _compile_keyword_block(body)
            subs: list[tuple[str, list[tuple[re.Pattern[str], str]]]] = []
            for sub_name, sub_body in (body.get("subcategories") or {}).items():
                subs.append((sub_name, _compile_keyword_block(sub_body)))
            compiled.append(_CompiledCategory(name=name, weight=weight,
                                              patterns=patterns,
                                              subcategories=subs))
        sections[section] = compiled
    return sections


class EditorialClassifier:
    """Editor-in-chief briefing the V-app CEO."""

    def __init__(self, yaml_path: Path = CATEGORIES_YAML):
        with yaml_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self._sections = _compile_categories(raw)

    @staticmethod
    def _haystack(article: RawArticle) -> str:
        parts = [article.title_original or "", article.content_snippet or ""]
        text = " ".join(parts)
        return text + " || " + _strip_accents(text)

    @staticmethod
    def _title_haystack(article: RawArticle) -> str:
        """Title-only haystack — used for player attribution.

        A player is the article's *subject* only when it appears in the
        title. A passing mention in the body (e.g. an Indonesia
        regulation article that mentions Grab once) should stay in
        Market Pulse, not be re-routed to Players Movement.
        """
        text = article.title_original or ""
        return text + " || " + _strip_accents(text)

    def _first_hit(
        self, haystack: str, cats: list[_CompiledCategory]
    ) -> CategoryHit | None:
        for cat in cats:
            for pat, kw in cat.patterns:
                if pat.search(haystack):
                    sub = None
                    for sub_name, sub_pats in cat.subcategories:
                        if any(p.search(haystack) for p, _ in sub_pats):
                            sub = sub_name
                            break
                    return CategoryHit(category=cat.name, subcategory=sub, keyword=kw)
        return None

    def _all_hits(
        self, haystack: str, cats: list[_CompiledCategory]
    ) -> list[tuple[str, int]]:
        """Return [(category_name, weight)] for every category that matches."""
        out: list[tuple[str, int]] = []
        seen: set[str] = set()
        for cat in cats:
            if cat.name in seen:
                continue
            for pat, _ in cat.patterns:
                if pat.search(haystack):
                    out.append((cat.name, cat.weight))
                    seen.add(cat.name)
                    break
        return out

    def _has_business_signal(self, haystack: str) -> tuple[bool, str | None]:
        for cat in self._sections.get("business_signals", []):
            for pat, _ in cat.patterns:
                if pat.search(haystack):
                    return True, cat.name
            for sub_name, sub_pats in cat.subcategories:
                for pat, _ in sub_pats:
                    if pat.search(haystack):
                        return True, f"{cat.name}/{sub_name}"
        return False, None

    def _matches_exclude_pattern(self, haystack: str) -> str | None:
        """Drop based on EXCLUDE keyword list from Excel Scanning sheet."""
        for cat in self._sections.get("exclude_patterns", []):
            for pat, _ in cat.patterns:
                if pat.search(haystack):
                    return cat.name
        return None

    def classify(self, article: RawArticle) -> RawArticle:
        haystack = self._haystack(article)
        title_haystack = self._title_haystack(article)

        # ---- Source-based player auto-tag ----
        # Articles from player blog sources belong to that player even
        # when the title is a generic promo line ("5.5 Sale", "Happy
        # Friday") that doesn't mention the brand.
        source_player = _player_for_source(article.source)

        # ---- Always compute metadata (used by Round 2 / sort / render) ----
        # tracked = subject of the article (player keyword in TITLE)
        # mentioned_anywhere = also includes passing mentions in body
        tracked = [n for n, _ in self._all_hits(
            title_haystack, self._sections.get("players", []))]
        if source_player and source_player not in tracked:
            tracked.insert(0, source_player)
        tracked_anywhere = [n for n, _ in self._all_hits(
            haystack, self._sections.get("players", []))]
        if source_player and source_player not in tracked_anywhere:
            tracked_anywhere.insert(0, source_player)
        adjacent = [n for n, _ in self._all_hits(
            haystack, self._sections.get("adjacent_players", []))]
        themes = self._all_hits(haystack, self._sections.get("strategic_themes", []))
        has_signal, signal_type = self._has_business_signal(haystack)

        score = sum(w for _, w in themes)
        if tracked:
            score += _TRACKED_PLAYER_BONUS
        if adjacent and not tracked:
            score += _ADJACENT_PLAYER_BONUS
        if has_signal:
            score += _BUSINESS_SIGNAL_BONUS

        # Mentioned players list includes passing-mention tracked + adjacent
        article._mentioned_players = ", ".join(tracked_anywhere + adjacent)  # type: ignore[attr-defined]
        article._business_signal = signal_type  # type: ignore[attr-defined]
        article._matched_themes = ", ".join(name for name, _ in themes)  # type: ignore[attr-defined]
        article._relevance_score = score  # type: ignore[attr-defined]

        # ---- Round 1 (Scanning) gates ----
        # Only TITLE-tracked players bypass noise/exclude (their own promo
        # & content all belong in Players Movement). Passing mentions in
        # body don't grant bypass — those go through the normal MP flow.
        if not tracked:
            # Gate 1: hard title noise (clickbait, ticker, gadget review).
            if _is_noise_title(article.title_original or ""):
                article.status = Status.FILTERED_OUT
                article._exclude_reason = "noise_title"  # type: ignore[attr-defined]
                return article

            # Gate 2: explicit exclude patterns from anh's Excel Scanning sheet.
            excl = self._matches_exclude_pattern(haystack)
            if excl is not None:
                article.status = Status.FILTERED_OUT
                article._exclude_reason = excl  # type: ignore[attr-defined]
                return article

        # Gate 3: must match Cluster 1 (player) OR Cluster 2 (vertical).
        # That's it — no signal / no threshold gating. We also accept a
        # strategic_theme hit as in-scope, since anh's editorial concerns
        # include policy keywords (Thông tư, VNeID…) that aren't in the
        # vertical keyword lists.
        in_scope = (
            bool(tracked) or bool(tracked_anywhere) or bool(adjacent)
            or bool(themes)
        )
        mp_hit = self._first_hit(haystack, self._sections.get("market_pulse", []))
        if mp_hit is not None:
            in_scope = True

        if not in_scope:
            article.status = Status.FILTERED_OUT
            article._exclude_reason = "no_player_or_vertical_match"  # type: ignore[attr-defined]
            return article

        # ---- Output classification ----
        if tracked:
            article.type = ArticleType.PLAYERS_MOVEMENT
            article.player = tracked[0]
            pm_hit = self._first_hit(
                haystack, self._sections.get("players_movement_categories", []))
            if pm_hit is not None:
                article.pre_category = (
                    f"{pm_hit.category}/{pm_hit.subcategory}"
                    if pm_hit.subcategory else pm_hit.category
                )
            else:
                article.pre_category = None
            return article

        article.type = ArticleType.MARKET_PULSE
        if mp_hit is not None:
            article.pre_category = (
                f"{mp_hit.category}/{mp_hit.subcategory}"
                if mp_hit.subcategory else mp_hit.category
            )
        else:
            article.pre_category = None
        return article


# Backwards-compatible alias for existing imports.
CategoryClassifier = EditorialClassifier


def apply_filter(articles: Iterable[RawArticle]) -> list[RawArticle]:
    """Classify and rank articles. Highest relevance first."""
    clf = EditorialClassifier()
    out: list[RawArticle] = []
    kept = filtered = 0
    for a in articles:
        clf.classify(a)
        if a.status == Status.FILTERED_OUT:
            filtered += 1
        else:
            kept += 1
        out.append(a)
    out.sort(key=lambda a: -getattr(a, "_relevance_score", 0))
    logger.info(
        "Round 1 (Scanning): kept={} filtered_out={}",
        kept, filtered,
    )
    return out
