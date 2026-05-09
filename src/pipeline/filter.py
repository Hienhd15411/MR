"""Editorial-grade filter for the V-app super-app Market Watch report.

Reads `src/config/categories.yaml` and acts as a chief editor briefing the
V-app CEO. For each article it computes:

  - mentioned_players  — tracked + adjacent player names found
  - business_signal    — what kind of action (Launch / Funding / …)
  - matched_themes     — V-app strategic themes touched + their weights
  - relevance_score    — weighted sum (drives report ordering & cut-off)
  - pre_category       — output classification (vertical or PM bucket)
  - type / player      — Market Pulse vs Players Movement attribution

A binary keep/drop decision is made AFTER scoring:

    KEEP if  business_signal AND (
                tracked_player                                # competitor news
                OR  matched_themes (any V-app strategic theme)  # in-scope
             )
    DROP otherwise — even if a vertical keyword matched.

This implements: vertical match alone is no longer enough; the article
must actually touch V-app's super-app strategy.
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

# Bonuses added on top of theme weights.
_TRACKED_PLAYER_BONUS = 5
_ADJACENT_PLAYER_BONUS = 1
_BUSINESS_SIGNAL_BONUS = 1
# Articles below this score are dropped even if a theme matched.
# Tuned for V-app CEO lens: needs at least one Tier-A theme (5) OR
# tracked player (5), plus a business signal (1).
_RELEVANCE_THRESHOLD = 4

# Title-level noise patterns. If the article title matches any of these,
# we drop it regardless of theme/player score — these are clickbait,
# opinion, explainer, lifestyle, ticker or rumour articles that aren't
# strategic intel even when they mention a tracked brand.
_NOISE_TITLE_PATTERNS = [
    # Question titles (opinion/explainer)
    re.compile(r"^\s*(vì sao|tại sao|liệu|có nên|làm sao|làm thế nào|điều gì)\b",
               re.IGNORECASE),
    re.compile(r"\?\s*$"),  # ends with ?
    # Lifestyle / health / clickbait
    re.compile(r"\b(bí quyết|mẹo|cách|tips|hướng dẫn)\s+",
               re.IGNORECASE),
    re.compile(r"\b(cảnh báo|đe doạ|hủy hoại|nguy cơ|bộ não|sức khỏe|sức khoẻ)\b",
               re.IGNORECASE),
    # Price tickers (commodity, not strategic)
    re.compile(r"\bgiá\s+(bitcoin|btc|eth|vàng|usd|xăng|dầu)\b", re.IGNORECASE),
    re.compile(r"\b(tỷ giá|tỉ giá)\b", re.IGNORECASE),
    re.compile(r"\bbitcoin hôm nay\b", re.IGNORECASE),
    # Rumours / leaks (gadget speculation)
    re.compile(r"\b(rò rỉ|lộ\s+(diện|thông tin|thiết kế|cấu hình|tính năng)|"
               r"có thể\s+(ra mắt|được ra mắt|khai tử)|"
               r"sắp\s+(khai tử|ngừng))\b", re.IGNORECASE),
    # Pure gadget reviews / preview titles
    re.compile(r"\b(đánh giá|review|so sánh|trên tay|hands-on)\b",
               re.IGNORECASE),
    # Personality / opinion
    re.compile(r"\b(tuyên bố|cảnh báo|tin rằng|nhận định|cho rằng|"
               r"khẳng định|chia sẻ)\b.+(:|—|–)", re.IGNORECASE),
    # Listicle markers
    re.compile(r"^\s*(top\s+\d+|\d+\s+(điều|cách|lý do|bí mật|mẹo))",
               re.IGNORECASE),
    # Quoted celebrity / influencer headlines (often opinion pieces)
    re.compile(r"^\s*[\w\s]+\s*[:：]\s*[\"“]"),
    # Title starts with emoji / pictogram (promo banner from blog feeds)
    re.compile(r"^\s*[\U0001F300-\U0001FAFF☀-➿]+"),
    # Vague promo titles (player blog noise)
    re.compile(r"^\s*(thông báo|thông cáo|sự kiện|cộng đồng|khuyến mãi|"
               r"thư viện|ưu đãi)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(grab|momo|zalo|shopee)\s+triển khai\s+chiến dịch mới\s*$",
               re.IGNORECASE),
    # Gadget release with price tag in title (consumer launch)
    re.compile(r"\bgiá\s+(từ\s+)?\d+([\.,]\d+)?\s*(triệu|tr|nghìn|usd|\$)",
               re.IGNORECASE),
    # Vehicle / motorbike releases
    re.compile(r"\bxe\s+(côn\s+tay|máy\s+điện|tay\s+ga|ga|máy)\b",
               re.IGNORECASE),
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

        # Hard noise gate: drop clickbait/opinion/ticker even if score is high.
        if _is_noise_title(article.title_original or ""):
            article.status = Status.FILTERED_OUT
            article._mentioned_players = ""  # type: ignore[attr-defined]
            article._business_signal = None  # type: ignore[attr-defined]
            article._matched_themes = ""  # type: ignore[attr-defined]
            article._relevance_score = 0  # type: ignore[attr-defined]
            article._exclude_reason = "noise_title"  # type: ignore[attr-defined]
            return article

        # Hard exclude gate: matches anh's Excel Scanning sheet exclusions.
        excl = self._matches_exclude_pattern(haystack)
        if excl is not None:
            article.status = Status.FILTERED_OUT
            article._mentioned_players = ""  # type: ignore[attr-defined]
            article._business_signal = None  # type: ignore[attr-defined]
            article._matched_themes = ""  # type: ignore[attr-defined]
            article._relevance_score = 0  # type: ignore[attr-defined]
            article._exclude_reason = excl  # type: ignore[attr-defined]
            return article

        tracked = [n for n, _ in self._all_hits(
            haystack, self._sections.get("players", []))]
        adjacent = [n for n, _ in self._all_hits(
            haystack, self._sections.get("adjacent_players", []))]
        themes = self._all_hits(haystack, self._sections.get("strategic_themes", []))
        has_signal, signal_type = self._has_business_signal(haystack)

        # Compute editorial relevance score
        score = sum(w for _, w in themes)
        if tracked:
            score += _TRACKED_PLAYER_BONUS
        if adjacent and not tracked:
            score += _ADJACENT_PLAYER_BONUS
        if has_signal:
            score += _BUSINESS_SIGNAL_BONUS

        # Stash editorial metadata on the article (consumed by sinks/render)
        article._mentioned_players = ", ".join(tracked + adjacent)  # type: ignore[attr-defined]
        article._business_signal = signal_type  # type: ignore[attr-defined]
        article._matched_themes = ", ".join(name for name, _ in themes)  # type: ignore[attr-defined]
        article._relevance_score = score  # type: ignore[attr-defined]

        # ---- Editorial decision ----
        # Hard requirement 1: must describe a business action.
        if not has_signal:
            article.status = Status.FILTERED_OUT
            return article

        # Hard requirement 2: must touch V-app strategy. Three valid paths:
        #   a) Tracked competitor (always interesting)
        #   b) Strategic theme match (super-app concern)
        #   c) Adjacent player + theme (industry context)
        in_scope = bool(tracked) or bool(themes)
        if not in_scope:
            article.status = Status.FILTERED_OUT
            return article

        # Hard requirement 3: relevance threshold (drops weak matches)
        if score < _RELEVANCE_THRESHOLD:
            article.status = Status.FILTERED_OUT
            return article

        # ---- Output classification (separate from filter) ----
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

        # Market Pulse — assign a vertical for output classification
        article.type = ArticleType.MARKET_PULSE
        mp_hit = self._first_hit(haystack, self._sections.get("market_pulse", []))
        if mp_hit is not None:
            article.pre_category = (
                f"{mp_hit.category}/{mp_hit.subcategory}"
                if mp_hit.subcategory else mp_hit.category
            )
        else:
            # Theme matched but no vertical keyword — still keep, AI will tag
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
        "Editorial filter: kept={} filtered_out={} (threshold={})",
        kept, filtered, _RELEVANCE_THRESHOLD,
    )
    return out
