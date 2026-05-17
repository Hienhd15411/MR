"""Markdown preview — grouped by topic_group → sub_topic_group.

Reads the private attrs the filter + scoring stages stash on each
article: _topic_group, _sub_topic_group, _signal_level, _signal_score,
_R1, _R2, _review_flag.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.storage.models import RawArticle


def _ga(a: RawArticle, attr: str, default=""):
    return getattr(a, attr, default)


def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _render_article(a: RawArticle, lines: list[str]) -> None:
    sig = _ga(a, "_signal_score", 0)
    lvl = _ga(a, "_signal_level", "")
    flag = " 🚩HUMAN_REVIEW" if _ga(a, "_review_flag", False) else ""
    lines.append(f"- **[{a.title_original}]({a.url})**{flag}")
    meta = [
        f"signal: `{sig}` ({lvl})",
        f"R1/R2: `{_ga(a, '_R1', '')}`/`{_ga(a, '_R2', '')}`",
        f"source: `{a.source}`",
        f"published: {_fmt_dt(a.published_date)}",
    ]
    lines.append("  - " + " · ".join(meta))
    if a.content_snippet:
        snip = a.content_snippet.replace("\n", " ").strip()[:300]
        lines.append(f"  - {snip}")
    lines.append("")


_MP_ORDER = ["Trong nước", "SEA", "Trung quốc", "Quốc tế"]


def render_markdown(articles: Iterable[RawArticle]) -> str:
    arts = list(articles)
    arts.sort(key=lambda a: -float(_ga(a, "_signal_score", 0) or 0))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pm = [a for a in arts if _ga(a, "_topic_group") == "Players Movement"]
    mp = [a for a in arts if _ga(a, "_topic_group") != "Players Movement"]
    flagged = [a for a in arts if _ga(a, "_review_flag", False)]

    lines: list[str] = [
        "# Market Watch — Database preview",
        "",
        f"- Generated: **{now}**",
        f"- Kept: **{len(arts)}** "
        f"(Market Pulse: {len(mp)} · Players Movement: {len(pm)})",
        f"- Flagged HUMAN_REVIEW: **{len(flagged)}**",
        "",
    ]

    # Signal-level distribution
    lvl_counts: dict[str, int] = {}
    for a in arts:
        lv = _ga(a, "_signal_level", "?")
        lvl_counts[lv] = lvl_counts.get(lv, 0) + 1
    lines.append("## Summary by signal level")
    lines.append("")
    lines.append("| Level | Count |")
    lines.append("|---|---:|")
    for lv in ["5 - Industry disruption", "4 - Strategic shift",
               "3 - Market signal", "2 - Minor signal", "1 - Noise"]:
        if lv in lvl_counts:
            lines.append(f"| {lv} | {lvl_counts[lv]} |")
    lines.append("")

    # Top 10
    if arts:
        lines.append("## Top 10 by signal score")
        lines.append("")
        for i, a in enumerate(arts[:10], 1):
            sig = _ga(a, "_signal_score", 0)
            lines.append(f"{i}. `[{sig}]` **{a.title_original}** "
                         f"· {_ga(a, '_sub_topic_group', '')}")
        lines.append("")

    # Players Movement — group by player
    if pm:
        lines.append(f"## Players Movement ({len(pm)})")
        lines.append("")
        by_player: dict[str, list[RawArticle]] = {}
        for a in pm:
            by_player.setdefault(_ga(a, "_sub_topic_group", "?"), []).append(a)
        for player, grp in sorted(by_player.items()):
            lines.append(f"### {player} ({len(grp)})")
            lines.append("")
            for a in grp:
                _render_article(a, lines)

    # Market Pulse — group by geography
    if mp:
        lines.append(f"## Market Pulse ({len(mp)})")
        lines.append("")
        by_geo: dict[str, list[RawArticle]] = {}
        for a in mp:
            by_geo.setdefault(_ga(a, "_sub_topic_group", "Quốc tế"), []).append(a)
        ordered = ([g for g in _MP_ORDER if g in by_geo]
                   + [g for g in by_geo if g not in _MP_ORDER])
        for geo in ordered:
            grp = by_geo[geo]
            lines.append(f"### {geo} ({len(grp)})")
            lines.append("")
            for a in grp:
                _render_article(a, lines)

    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, articles: Iterable[RawArticle]) -> int:
    arts = list(articles)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(arts), encoding="utf-8")
    return len(arts)
