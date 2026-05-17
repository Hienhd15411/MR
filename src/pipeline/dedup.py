"""Deduplication — Market Watch Crawler Instructions v2, Section 4.

Two articles are the "same event" when ALL hold:
  1. Jaccard title similarity >= 0.70  (token overlap; no AI SDK)
  2. publish_date within 48h
  3. share >= 1 main entity token (proper-noun-ish overlap)

Keep rule when duplicates found:
  1. highest source priority (0 > 1 > 2 > 3)
  2. else longer content_snippet
  3. else Vietnamese over English (heuristic: has VN diacritics)
The losers are returned as discarded with reason DUPLICATE_OF_<id>.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import timedelta

from loguru import logger

from src.storage.models import RawArticle, Status

_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹ]+", re.UNICODE)
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with",
    "và", "của", "cho", "trên", "trong", "với", "là", "các", "một", "được",
    "tại", "từ", "đã", "sẽ", "this", "that", "new", "mới",
}


def _tokens(title: str) -> set[str]:
    return {
        t.lower() for t in _TOKEN_RE.findall(title or "")
        if len(t) > 1 and t.lower() not in _STOP
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _has_vn_diacritics(text: str) -> bool:
    return any(
        unicodedata.combining(c) for c in unicodedata.normalize("NFD", text or "")
    )


def _within_48h(a: RawArticle, b: RawArticle) -> bool:
    if a.published_date is None or b.published_date is None:
        return True  # unknown dates → don't block dedup
    return abs(a.published_date - b.published_date) <= timedelta(hours=48)


def _keep_winner(x: RawArticle, y: RawArticle) -> tuple[RawArticle, RawArticle]:
    """Return (winner, loser)."""
    px = getattr(x, "_source_priority", 1)
    py = getattr(y, "_source_priority", 1)
    if px != py:
        return (x, y) if px < py else (y, x)
    lx = len(x.content_snippet or "")
    ly = len(y.content_snippet or "")
    if lx != ly:
        return (x, y) if lx > ly else (y, x)
    vx = _has_vn_diacritics(x.title_original)
    vy = _has_vn_diacritics(y.title_original)
    if vx != vy:
        return (x, y) if vx else (y, x)
    return (x, y)


def deduplicate(
    articles: list[RawArticle],
) -> tuple[list[RawArticle], list[RawArticle]]:
    """Returns (unique, duplicates). Duplicates get
    _discard_reason = 'DUPLICATE_OF_<winner id>'."""
    kept: list[RawArticle] = []
    dups: list[RawArticle] = []
    token_cache: list[tuple[RawArticle, set[str]]] = []

    for a in articles:
        a_tok = _tokens(a.title_original)
        matched_winner = None
        for idx, (k, k_tok) in enumerate(token_cache):
            if not _within_48h(a, k):
                continue
            sim = _jaccard(a_tok, k_tok)
            shared_entity = len(a_tok & k_tok) >= 3
            if sim >= 0.70 or shared_entity:
                winner, loser = _keep_winner(k, a)
                if winner is a:
                    # incoming wins — swap out the cached one
                    loser._discard_reason = (  # type: ignore[attr-defined]
                        f"DUPLICATE_OF_{a.id}")
                    loser.status = Status.FILTERED_OUT
                    dups.append(loser)
                    kept[idx] = a
                    token_cache[idx] = (a, a_tok)
                else:
                    a._discard_reason = (  # type: ignore[attr-defined]
                        f"DUPLICATE_OF_{k.id}")
                    a.status = Status.FILTERED_OUT
                    dups.append(a)
                matched_winner = winner
                break
        if matched_winner is None:
            kept.append(a)
            token_cache.append((a, a_tok))

    logger.info("Dedup: unique={} duplicates={}", len(kept), len(dups))
    return kept, dups
