from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.storage.models import ArticleType, RawArticle, Status


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _category_bucket(pre_category: str | None) -> str:
    """Top-level PM bucket from `pre_category` (Category/Subcategory)."""
    if not pre_category:
        return "Khác"
    return pre_category.split("/")[0].strip() or "Khác"


# Ordering inside each player section (matches Weekly Market Watch template)
_PM_CATEGORY_ORDER = [
    "Strategy",
    "Product",
    "Feature",
    "Partnership",
    "Marketing",   # vouchers / khuyến mãi
    "CSR/ Community",
    "Khác",
]


def _render_article(a: RawArticle, lines: list[str]) -> None:
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


def _render_section(title: str, items: list[RawArticle], lines: list[str]) -> None:
    """Generic group-by-source rendering (used for Market Pulse)."""
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
            _render_article(a, lines)


def _render_pm_grouped(items: list[RawArticle], lines: list[str]) -> None:
    """Players Movement — group by player → then by category.

    Matches the Weekly Market Watch template structure:
        ## Players Movement (N)
        ### MoMo (X)
            Marketing — Voucher / Khuyến mãi (12)
              - ...
            Product (2)
            Partnership (3)
        ### Zalo (Y)
            ...
    """
    if not items:
        return
    lines.append(f"## Players Movement ({len(items)})")
    lines.append("")

    by_player: dict[str, list[RawArticle]] = {}
    for a in items:
        by_player.setdefault(a.player or "Không xác định", []).append(a)

    for player, group in sorted(by_player.items()):
        lines.append(f"### {player} ({len(group)})")
        lines.append("")

        # Bucket by top-level category
        by_cat: dict[str, list[RawArticle]] = {}
        for a in group:
            by_cat.setdefault(_category_bucket(a.pre_category), []).append(a)

        # Render in template order
        ordered_keys = (
            [k for k in _PM_CATEGORY_ORDER if k in by_cat]
            + [k for k in by_cat if k not in _PM_CATEGORY_ORDER]
        )
        for cat in ordered_keys:
            cat_items = by_cat[cat]
            cat_label = "Marketing — Voucher / Khuyến mãi" if cat == "Marketing" else cat
            lines.append(f"#### {cat_label} ({len(cat_items)})")
            lines.append("")
            for a in cat_items:
                _render_article(a, lines)


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

    # ---- Summary by relevance score band ----
    bands = [
        ("🔥 Must-read", 10, 999, "Tracked player + Tier-A theme + signal"),
        ("✅ Strong",     7,  9,   "Tracked player or multi-theme match"),
        ("🟢 Moderate",   4,  6,   "Single theme + signal"),
        ("🟡 Context",    1,  3,   "Adjacent player / weak signal"),
        ("⚪ Noise",      0,  0,   "No theme/signal — borderline keep"),
    ]
    band_buckets: dict[str, tuple[int, list[RawArticle]]] = {
        name: (0, []) for name, *_ in bands
    }
    for a in kept:
        score = getattr(a, "_relevance_score", 0)
        for name, lo, hi, _ in bands:
            if lo <= score <= hi:
                cnt, items = band_buckets[name]
                band_buckets[name] = (cnt + 1, items + [a])
                break

    lines.append("## Summary by relevance score")
    lines.append("")
    lines.append("| Band | Score range | Count | Meaning |")
    lines.append("|---|---:|---:|---|")
    for name, lo, hi, meaning in bands:
        cnt = band_buckets[name][0]
        rng = f"{lo}-{hi}" if hi != 999 else f"{lo}+"
        lines.append(f"| {name} | `{rng}` | {cnt} | {meaning} |")
    lines.append("")

    # ---- Top 10 highest-relevance preview ----
    top10 = sorted(kept, key=lambda a: -getattr(a, "_relevance_score", 0))[:10]
    if top10:
        lines.append("## Top 10 highest relevance")
        lines.append("")
        for i, a in enumerate(top10, 1):
            score = getattr(a, "_relevance_score", 0)
            player_tag = f" · *{a.player}*" if a.player else ""
            lines.append(f"{i}. `[{score}]` **{a.title_original}**{player_tag}")
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
    _render_pm_grouped(players_movement, lines)

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
