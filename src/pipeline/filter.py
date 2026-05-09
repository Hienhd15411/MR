"""Keyword-based filter and pre-categorisation.

Reads `src/config/categories.yaml`, then for each article:
  - matches title + snippet against keyword lists with word boundaries
  - sets `pre_category` (e.g. "AI", "Fintech/E-wallet", "Marketing")
  - if a Player keyword matches, reclassifies as players_movement
    and fills `player`
  - articles with no category match are kept but flagged
    `status=filtered_out` for downstream review
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from loguru import logger

from src.config.settings import SOURCES_YAML  # noqa: F401  (import for path consistency)
from src.storage.models import ArticleType, RawArticle, Status

CATEGORIES_YAML = Path(__file__).resolve().parents[1] / "config" / "categories.yaml"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _is_acronym(keyword: str) -> bool:
    """All-uppercase ASCII tokens like AI, LLM, GPT, BNPL, GMV are acronyms.

    Case-sensitive matching prevents false positives such as Vietnamese
    "ai" (pronoun) matching the AI keyword.
    """
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
    patterns: list[tuple[re.Pattern[str], str]]
    subcategories: list[tuple[str, list[tuple[re.Pattern[str], str]]]]


def _compile_keyword_block(block: dict) -> list[tuple[re.Pattern[str], str]]:
    out: list[tuple[re.Pattern[str], str]] = []
    for kw in block.get("keywords", []) or []:
        cs = _is_acronym(kw)
        out.append((_build_pattern(kw, case_sensitive=cs), kw))
        # Accent-stripped fallback for VN-diacritic keywords, but skip
        # short single-syllable words where stripping causes collisions
        # (e.g. "dừng" stripped → "dung" collides with "dùng").
        accent_free = _strip_accents(kw)
        if accent_free != kw and len(accent_free) >= 6 and " " in accent_free.strip():
            out.append((_build_pattern(accent_free, case_sensitive=False), kw))
    return out


def _compile_categories(raw: dict) -> dict[str, list[_CompiledCategory]]:
    """Returns {section: [_CompiledCategory, ...]}."""
    sections: dict[str, list[_CompiledCategory]] = {}
    for section, cats in raw.items():
        if not isinstance(cats, dict):
            continue
        compiled: list[_CompiledCategory] = []
        for name, body in cats.items():
            body = body or {}
            patterns = _compile_keyword_block(body)
            subs: list[tuple[str, list[tuple[re.Pattern[str], str]]]] = []
            for sub_name, sub_body in (body.get("subcategories") or {}).items():
                subs.append((sub_name, _compile_keyword_block(sub_body)))
            compiled.append(_CompiledCategory(name=name, patterns=patterns,
                                              subcategories=subs))
        sections[section] = compiled
    return sections


class CategoryClassifier:
    def __init__(self, yaml_path: Path = CATEGORIES_YAML):
        with yaml_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self._sections = _compile_categories(raw)

    @staticmethod
    def _haystack(article: RawArticle) -> str:
        parts = [article.title_original or "", article.content_snippet or ""]
        text = " ".join(parts)
        # Keep both accented and accent-stripped forms in the haystack so
        # patterns built from either form will hit.
        return text + " || " + _strip_accents(text)

    def _first_hit(
        self,
        haystack: str,
        cats: list[_CompiledCategory],
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

    def _all_player_hits(
        self, haystack: str, cats: list[_CompiledCategory]
    ) -> list[str]:
        """Return all distinct player names whose keywords match."""
        out: list[str] = []
        for cat in cats:
            for pat, _ in cat.patterns:
                if pat.search(haystack):
                    if cat.name not in out:
                        out.append(cat.name)
                    break
        return out

    def _has_business_signal(self, haystack: str) -> tuple[bool, str | None]:
        """Executive-grade gate: drop articles without a business action.

        Returns (matched?, signal_category). Articles that mention a
        player/brand but don't describe a strategic move (launch, M&A,
        funding, regulation, partnership, performance numbers, pricing,
        expansion, product/feature update, marketing campaign) are
        considered noise and filtered out.
        """
        signals = self._sections.get("business_signals", [])
        for cat in signals:
            for pat, _ in cat.patterns:
                if pat.search(haystack):
                    return True, cat.name
            for sub_name, sub_pats in cat.subcategories:
                for pat, _ in sub_pats:
                    if pat.search(haystack):
                        return True, f"{cat.name}/{sub_name}"
        return False, None

    def classify(self, article: RawArticle) -> RawArticle:
        haystack = self._haystack(article)
        tracked_cats = self._sections.get("players", [])
        adjacent_cats = self._sections.get("adjacent_players", [])

        tracked = self._all_player_hits(haystack, tracked_cats)
        adjacent = self._all_player_hits(haystack, adjacent_cats)
        article._mentioned_players = ", ".join(tracked + adjacent)  # type: ignore[attr-defined]

        # Business signal gate — REQUIRED for all paths.
        has_signal, signal = self._has_business_signal(haystack)
        article._business_signal = signal  # type: ignore[attr-defined]

        # 1) Tracked player → players_movement (still needs business signal)
        if tracked:
            if not has_signal:
                article.status = Status.FILTERED_OUT
                article.pre_category = None
                return article
            article.type = ArticleType.PLAYERS_MOVEMENT
            article.player = tracked[0]
            pm_cats = self._sections.get("players_movement_categories", [])
            pm_hit = self._first_hit(haystack, pm_cats)
            if pm_hit is not None:
                article.pre_category = (
                    f"{pm_hit.category}/{pm_hit.subcategory}"
                    if pm_hit.subcategory else pm_hit.category
                )
            else:
                article.pre_category = None
                article.status = Status.FILTERED_OUT
            return article

        # 2) Otherwise market_pulse keyword categories
        mp_hit = self._first_hit(haystack, self._sections.get("market_pulse", []))
        if mp_hit is not None:
            if not has_signal:
                article.status = Status.FILTERED_OUT
                article.pre_category = None
                return article
            article.type = ArticleType.MARKET_PULSE
            article.pre_category = (
                f"{mp_hit.category}/{mp_hit.subcategory}"
                if mp_hit.subcategory else mp_hit.category
            )
            return article

        # 3) Adjacent player only — keep only if there's a business signal
        if adjacent and has_signal:
            article.type = ArticleType.MARKET_PULSE
            article.pre_category = None
            return article

        # 4) No match → drop
        article.status = Status.FILTERED_OUT
        return article


def apply_filter(articles: Iterable[RawArticle]) -> list[RawArticle]:
    """Classify all articles in place and return them."""
    clf = CategoryClassifier()
    out: list[RawArticle] = []
    kept = filtered = 0
    for a in articles:
        clf.classify(a)
        if a.status == Status.FILTERED_OUT:
            filtered += 1
        else:
            kept += 1
        out.append(a)
    logger.info("Filter: kept={} filtered_out={}", kept, filtered)
    return out
