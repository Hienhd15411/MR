"""4-Tier filter — Market Watch Crawler Instructions v2, Section 2.

Decision per article (source_priority comes from sources.yaml):

    IF source_priority == 0:              KEEP, Players Movement
    ELSE:
      has_t1, has_t3 (exception-aware), t2_count, t4_trigger
      IF has_t1 AND has_t3:               KEEP + HUMAN_REVIEW (Tier 4)
      ELIF has_t3:                         DISCARD  (T3 reason code)
      ELIF has_t1:                         KEEP
      ELIF t2_count >= 2:                  KEEP
      ELIF t4_trigger:                     KEEP + HUMAN_REVIEW
      ELSE:                                DISCARD  (NO_KEYWORD)

Also computes (Section 2.5 / 2.6):
  - topic_group       Market Pulse | Players Movement
  - sub_topic_group   geography (Trong nước/SEA/Trung quốc/Quốc tế) or player
  - review_flag       True when HUMAN_REVIEW
  - discard_reason    code when discarded (else "")
The chosen verdict is stashed on the article as private attributes
consumed by the scoring stage + the Excel sinks.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml
from loguru import logger

from src.storage.models import ArticleType, RawArticle, Status

TIERS_YAML = Path(__file__).resolve().parents[1] / "config" / "tiers.yaml"
SOURCES_YAML = Path(__file__).resolve().parents[1] / "config" / "sources.yaml"


# ---------------------------------------------------------------------------
# keyword pattern helpers (word-boundary, accent-aware, acronym-safe)
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _is_acronym(kw: str) -> bool:
    kw = kw.strip()
    if not kw or " " in kw or len(kw) > 8 or not kw.isascii():
        return False
    return kw.isupper() and any(c.isalpha() for c in kw)


def _pattern(keyword: str) -> re.Pattern[str]:
    kw = keyword.strip()
    flags = re.UNICODE
    if not _is_acronym(kw):
        flags |= re.IGNORECASE
    return re.compile(rf"(?<![\w]){re.escape(kw)}(?![\w])", flags)


def _compile_list(words: Iterable[str]) -> list[re.Pattern[str]]:
    pats: list[re.Pattern[str]] = []
    for w in words:
        if not w:
            continue
        pats.append(_pattern(w))
        accent_free = _strip_accents(w)
        if accent_free != w and len(accent_free) >= 6 and " " in accent_free.strip():
            pats.append(_pattern(accent_free))
    return pats


def _any(pats: list[re.Pattern[str]], hay: str) -> bool:
    return any(p.search(hay) for p in pats)


def _count(pats: list[re.Pattern[str]], hay: str) -> int:
    return sum(1 for p in pats if p.search(hay))


@dataclass
class _Tier3Block:
    code: str
    keywords: list[re.Pattern[str]]
    exception: list[re.Pattern[str]]


@dataclass
class FilterVerdict:
    keep: bool
    topic_group: str = "Market Pulse"
    sub_topic_group: str = "Quốc tế"
    review_flag: bool = False
    discard_reason: str = ""
    matched_keywords: list[str] = field(default_factory=list)


def _source_priority_map() -> dict[str, int]:
    with SOURCES_YAML.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    out: dict[str, int] = {}
    for section in ("news", "players"):
        for entry in cfg.get(section) or []:
            out[entry["key"]] = int(entry.get("priority", 1))
    return out


class TierFilter:
    def __init__(self, tiers_path: Path = TIERS_YAML):
        with tiers_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # Flatten Tier-1 and Tier-2 keyword groups
        self._t1 = _compile_list(
            kw for grp in (raw.get("tier1") or {}).values() for kw in grp
        )
        self._t1_words = [
            kw for grp in (raw.get("tier1") or {}).values() for kw in grp
        ]
        self._t2 = _compile_list(
            kw for grp in (raw.get("tier2") or {}).values() for kw in grp
        )

        self._t3: list[_Tier3Block] = []
        for blk in (raw.get("tier3") or {}).values():
            self._t3.append(
                _Tier3Block(
                    code=blk.get("code", "T3"),
                    keywords=_compile_list(blk.get("keywords") or []),
                    exception=_compile_list(blk.get("exception") or []),
                )
            )

        geo = raw.get("geography") or {}
        self._geo_vn = _compile_list(geo.get("vn") or [])
        self._geo_sea = _compile_list(geo.get("sea") or [])
        self._geo_tq = _compile_list(geo.get("tq") or [])

        self._priority = _source_priority_map()

    # ---- helpers -------------------------------------------------------

    @staticmethod
    def _haystack(a: RawArticle) -> str:
        text = f"{a.title_original or ''} {a.content_snippet or ''}"
        return text + " || " + _strip_accents(text)

    def _geography(self, hay: str) -> str:
        if _any(self._geo_vn, hay):
            return "Trong nước"
        if _any(self._geo_sea, hay):
            return "SEA"
        if _any(self._geo_tq, hay):
            return "Trung quốc"
        return "Quốc tế"

    def _tier3_hit(self, hay: str) -> tuple[bool, str]:
        """Return (fired, code). A block fires only if a keyword matches
        AND no exception keyword matches."""
        for blk in self._t3:
            if _any(blk.keywords, hay):
                if blk.exception and _any(blk.exception, hay):
                    continue  # exception rescues it
                return True, blk.code
        return False, ""

    # ---- main ----------------------------------------------------------

    def classify(self, a: RawArticle, source_key: str) -> FilterVerdict:
        hay = self._haystack(a)
        priority = self._priority.get(source_key, 1)

        # Section 2.6 / 2.5 geography first (always computed)
        geo = self._geography(hay)

        # Priority 0 — player blog → always KEEP, Players Movement
        if priority == 0:
            v = FilterVerdict(keep=True, topic_group="Players Movement",
                              sub_topic_group=a.player or "Players")
            return v

        has_t1 = _any(self._t1, hay)
        t3_fired, t3_code = self._tier3_hit(hay)
        t2_count = _count(self._t2, hay)

        # Tier-4 ambiguity triggers (Section 2.4).
        # NOT a blanket keep: only when there's a weak signal worth a
        # human glance — clickbait-prone source, OR exactly one Tier-2
        # keyword in a too-short article.
        short_article = len((a.content_snippet or "").split()) < 30
        t4_trigger = (priority == 3 and t2_count >= 1) or (
            t2_count == 1 and short_article
        )

        topic_group = "Market Pulse"
        sub_topic = geo
        # Player-movement detection (Section 2.6) for non-priority-0
        if a.player and a.type == ArticleType.PLAYERS_MOVEMENT:
            topic_group = "Players Movement"
            sub_topic = a.player

        # Decision tree (Section 2)
        if has_t1 and t3_fired:
            return FilterVerdict(keep=True, topic_group=topic_group,
                                 sub_topic_group=sub_topic, review_flag=True)
        if t3_fired:
            return FilterVerdict(keep=False, discard_reason=t3_code)
        if has_t1:
            return FilterVerdict(keep=True, topic_group=topic_group,
                                 sub_topic_group=sub_topic)
        if t2_count >= 2:
            return FilterVerdict(keep=True, topic_group=topic_group,
                                 sub_topic_group=sub_topic)
        if t4_trigger:
            return FilterVerdict(keep=True, topic_group=topic_group,
                                 sub_topic_group=sub_topic, review_flag=True)
        return FilterVerdict(keep=False, discard_reason="NO_KEYWORD")


def apply_filter(
    articles: Iterable[tuple[RawArticle, str]]
) -> tuple[list[RawArticle], list[RawArticle]]:
    """Classify (article, source_key) pairs.

    Returns (kept, discarded). Verdict fields are stashed on each
    article as private attrs for the scoring stage + Excel sinks.
    """
    flt = TierFilter()
    kept: list[RawArticle] = []
    discarded: list[RawArticle] = []
    flagged = 0
    for a, src in articles:
        v = flt.classify(a, src)
        a._topic_group = v.topic_group              # type: ignore[attr-defined]
        a._sub_topic_group = v.sub_topic_group      # type: ignore[attr-defined]
        a._review_flag = v.review_flag              # type: ignore[attr-defined]
        a._discard_reason = v.discard_reason        # type: ignore[attr-defined]
        if v.keep:
            a.status = Status.NEW
            kept.append(a)
            if v.review_flag:
                flagged += 1
        else:
            a.status = Status.FILTERED_OUT
            discarded.append(a)
    logger.info(
        "Tier filter: kept={} discarded={} flagged_human_review={}",
        len(kept), len(discarded), flagged,
    )
    return kept, discarded


# Backwards-compatible alias for older imports/tests.
CategoryClassifier = TierFilter
EditorialClassifier = TierFilter
