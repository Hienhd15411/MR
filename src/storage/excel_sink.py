from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.storage.models import ArticleType, RawArticle, Status
from src.storage.schema import RAW_TAB, SHEET_HEADERS

_HEADER_FILL = PatternFill(start_color="FF1F4E78", end_color="FF1F4E78", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFFFF")
_COL_WIDTHS = {
    "id": 18, "crawled_at": 22, "source": 22, "source_type": 12, "url": 50,
    "title_original": 60, "content_snippet": 70, "published_date": 22,
    "type": 18, "pre_category": 18, "player": 12, "scope": 14, "status": 14,
}


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _row(a: RawArticle) -> list:
    return [
        a.id, _fmt_dt(a.crawled_at), a.source, a.source_type.value, a.url,
        a.title_original, a.content_snippet, _fmt_dt(a.published_date),
        a.type.value, a.pre_category or "", a.player or "", a.scope.value,
        a.status.value,
    ]


def _make_sheet(wb: Workbook, name: str, items: list[RawArticle]):
    ws = wb.create_sheet(name) if name != wb.active.title else wb.active
    if ws.title != name:
        ws.title = name
    ws.append(SHEET_HEADERS)
    for col_idx, header in enumerate(SHEET_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = _COL_WIDTHS.get(header, 18)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(SHEET_HEADERS))}1"
    for a in items:
        ws.append(_row(a))
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    return ws


def write_excel(path: Path, articles: Iterable[RawArticle]) -> int:
    arts = list(articles)
    arts.sort(
        key=lambda a: (a.published_date or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    kept = [a for a in arts if a.status != Status.FILTERED_OUT]
    dropped = [a for a in arts if a.status == Status.FILTERED_OUT]

    market_pulse = [a for a in kept if a.type == ArticleType.MARKET_PULSE]
    players_movement = [a for a in kept if a.type == ArticleType.PLAYERS_MOVEMENT]

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    # Replace default sheet with raw_data (kept-only).
    wb.active.title = "_tmp"
    _make_sheet(wb, RAW_TAB, kept)

    _make_sheet(wb, "market_pulse", market_pulse)
    _make_sheet(wb, "players_movement", players_movement)
    _make_sheet(wb, "filtered_out", dropped)

    # Drop the placeholder sheet.
    if "_tmp" in wb.sheetnames:
        del wb["_tmp"]
    # Make raw_data the first/active tab.
    wb.move_sheet(RAW_TAB, offset=-wb.sheetnames.index(RAW_TAB))
    wb.active = wb.sheetnames.index(RAW_TAB)

    # Summary sheet
    summary = wb.create_sheet("summary")
    summary.append(["bucket", "count"])
    for c in summary[1]:
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
    summary.append(["crawled_total", len(arts)])
    summary.append(["kept", len(kept)])
    summary.append(["market_pulse", len(market_pulse)])
    summary.append(["players_movement", len(players_movement)])
    summary.append(["filtered_out", len(dropped)])
    summary.append([])
    summary.append(["category", "count"])
    cat_counts: dict[str, int] = {}
    for a in kept:
        cat_counts[a.pre_category or "—"] = cat_counts.get(a.pre_category or "—", 0) + 1
    for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        summary.append([cat, n])
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 10

    wb.save(path)
    return len(kept)
