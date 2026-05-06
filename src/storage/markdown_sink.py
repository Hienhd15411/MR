from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.storage.models import RawArticle


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_markdown(articles: Iterable[RawArticle]) -> str:
    arts = list(articles)
    arts.sort(key=lambda a: (a.published_date or datetime.min.replace(tzinfo=timezone.utc)),
              reverse=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append(f"# Market Watch — raw_data preview")
    lines.append("")
    lines.append(f"- Generated: **{now}**")
    lines.append(f"- Articles: **{len(arts)}**")
    lines.append("")

    by_source: dict[str, list[RawArticle]] = {}
    for a in arts:
        by_source.setdefault(a.source, []).append(a)

    lines.append("## Summary by source")
    lines.append("")
    lines.append("| Source | Count |")
    lines.append("|---|---:|")
    for src, items in sorted(by_source.items()):
        lines.append(f"| {src} | {len(items)} |")
    lines.append("")

    lines.append("## Articles")
    lines.append("")
    for src, items in sorted(by_source.items()):
        lines.append(f"### {src} ({len(items)})")
        lines.append("")
        for a in items:
            lines.append(f"- **[{a.title_original}]({a.url})**")
            meta = (
                f"  - id: `{a.id}` · type: `{a.type.value}` · "
                f"scope: `{a.scope.value}` · "
                f"category: `{a.pre_category or '—'}`"
                + (f" · player: `{a.player}`" if a.player else "")
                + f" · status: `{a.status.value}` · "
                f"published: {_fmt_dt(a.published_date)}"
            )
            lines.append(meta)
            if a.content_snippet:
                snippet = a.content_snippet.replace("\n", " ").strip()
                lines.append(f"  - {snippet}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, articles: Iterable[RawArticle]) -> int:
    arts = list(articles)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(arts), encoding="utf-8")
    return len(arts)
