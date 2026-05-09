from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.storage.models import ArticleType, RawArticle, Status


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _render_section(title: str, items: list[RawArticle], lines: list[str]) -> None:
    if not items:
        return
    lines.append(f"## {title} ({len(items)})")
    lines.append("")
    by_source: dict[str, list[RawArticle]] = {}
    for a in items:
        by_source.setdefault(a.source, []).append(a)
    for src, group in sorted(by_source.items()):
        lines.append(f"### {src} ({len(group)})")
        lines.append("")
        for a in group:
            score = getattr(a, "_relevance_score", 0)
            themes = getattr(a, "_matched_themes", "") or ""
            signal = getattr(a, "_business_signal", "") or ""
            lines.append(f"- **[{a.title_original}]({a.url})**")
            meta_parts = [
                f"relevance: `{score}`",
                f"category: `{a.pre_category or '—'}`",
                f"scope: `{a.scope.value}`",
                f"published: {_fmt_dt(a.published_date)}",
            ]
            if a.player:
                meta_parts.insert(2, f"player: `{a.player}`")
            lines.append("  - " + " · ".join(meta_parts))
            if themes:
                lines.append(f"  - themes: {themes}")
            if signal:
                lines.append(f"  - signal: {signal}")
            if a.content_snippet:
                snippet = a.content_snippet.replace("\n", " ").strip()
                lines.append(f"  - {snippet}")
            lines.append("")


def render_markdown(articles: Iterable[RawArticle]) -> str:
    arts = list(articles)
    arts.sort(
        key=lambda a: (
            -getattr(a, "_relevance_score", 0),
            -(a.published_date or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
        ),
    )

    kept = [a for a in arts if a.status != Status.FILTERED_OUT]
    dropped = [a for a in arts if a.status == Status.FILTERED_OUT]

    market_pulse = [a for a in kept if a.type == ArticleType.MARKET_PULSE]
    players_movement = [a for a in kept if a.type == ArticleType.PLAYERS_MOVEMENT]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# Market Watch — raw_data preview")
    lines.append("")
    lines.append(f"- Generated: **{now}**")
    lines.append(f"- Crawled: **{len(arts)}**")
    lines.append(
        f"- Kept: **{len(kept)}** "
        f"(Market Pulse: {len(market_pulse)} · Players Movement: {len(players_movement)})"
    )
    lines.append(f"- Filtered out (no category match): **{len(dropped)}**")
    lines.append("")

    # Per-category summary for kept articles
    cat_counts: dict[str, int] = {}
    for a in kept:
        cat_counts[a.pre_category or "—"] = cat_counts.get(a.pre_category or "—", 0) + 1
    if cat_counts:
        lines.append("## Summary by category (kept only)")
        lines.append("")
        lines.append("| Category | Count |")
        lines.append("|---|---:|")
        for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {n} |")
        lines.append("")

    _render_section("Market Pulse", market_pulse, lines)
    _render_section("Players Movement", players_movement, lines)

    if dropped:
        lines.append("---")
        lines.append("")
        lines.append(
            f"## Filtered out ({len(dropped)}) — for audit, not included in report"
        )
        lines.append("")
        lines.append(
            "These articles were crawled but did not match any tracked category "
            "(AI, Chat, TMĐT, Travel, Ride/Food delivery, Fintech/E-wallet, Ticket) "
            "nor mention a tracked player (MoMo, Grab)."
        )
        lines.append("")
        for a in dropped[:50]:  # cap to keep file readable
            lines.append(
                f"- [{a.title_original}]({a.url}) — `{a.source}` · "
                f"published: {_fmt_dt(a.published_date)}"
            )
        if len(dropped) > 50:
            lines.append(f"- … and {len(dropped) - 50} more (see Sheet/xlsx)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, articles: Iterable[RawArticle]) -> int:
    arts = list(articles)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(arts), encoding="utf-8")
    return sum(1 for a in arts if a.status != Status.FILTERED_OUT)
