from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.storage.models import RawArticle
from src.storage.schema import RAW_TAB, SHEET_HEADERS

_HEADER_FILL = PatternFill(start_color="FF1F4E78", end_color="FF1F4E78", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFFFF")
_COL_WIDTHS = {
    "id": 18,
    "crawled_at": 22,
    "source": 22,
    "source_type": 12,
    "url": 50,
    "title_original": 60,
    "content_snippet": 70,
    "published_date": 22,
    "type": 18,
    "pre_category": 16,
    "player": 12,
    "scope": 14,
    "status": 12,
}


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def write_excel(path: Path, articles: Iterable[RawArticle]) -> int:
    arts = list(articles)
    arts.sort(
        key=lambda a: (a.published_date or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = RAW_TAB

    ws.append(SHEET_HEADERS)
    for col_idx, header in enumerate(SHEET_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = _COL_WIDTHS.get(header, 18)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(SHEET_HEADERS))}1"

    for a in arts:
        ws.append([
            a.id,
            _fmt_dt(a.crawled_at),
            a.source,
            a.source_type.value,
            a.url,
            a.title_original,
            a.content_snippet,
            _fmt_dt(a.published_date),
            a.type.value,
            a.pre_category or "",
            a.player or "",
            a.scope.value,
            a.status.value,
        ])

    # Wrap long text columns
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    # Add a second sheet with per-source counts as a quick summary.
    summary = wb.create_sheet("summary")
    summary.append(["source", "count"])
    for c in summary[1]:
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
    by_source: dict[str, int] = {}
    for a in arts:
        by_source[a.source] = by_source.get(a.source, 0) + 1
    for src, n in sorted(by_source.items()):
        summary.append([src, n])
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 10

    wb.save(path)
    return len(arts)
