"""Extract promo start/end dates from article text (Section 5 col 17-18).

Vietnamese promo phrasing patterns:
  "từ ngày 24/04 đến 05/05/2026"
  "từ 24/4 - 5/5"
  "áp dụng từ 01/03/2026"
  "đến hết 31/5"
  "hiệu lực từ 28/04/2026"
  "kết thúc vào 10/05"
Returns (start, end) as 'DD/MM/YYYY' strings or "".
"""
from __future__ import annotations

import re
from datetime import datetime

_DMY = r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?"
_RANGE = re.compile(
    rf"(?:từ|from)?\s*(?:ngày\s*)?{_DMY}\s*(?:-|–|—|đến|to|tới)\s*"
    rf"(?:hết\s*)?(?:ngày\s*)?{_DMY}",
    re.IGNORECASE,
)
_START = re.compile(
    rf"(?:từ|áp dụng từ|hiệu lực từ|bắt đầu từ|ra mắt từ|from)\s*"
    rf"(?:ngày\s*)?{_DMY}", re.IGNORECASE,
)
_END = re.compile(
    rf"(?:đến hết|kết thúc vào|hết hiệu lực|đến ngày|đến|until|hạn)\s*"
    rf"(?:ngày\s*)?{_DMY}", re.IGNORECASE,
)


def _norm(d: str, m: str, y: str | None) -> str:
    try:
        di, mi = int(d), int(m)
        yi = int(y) if y else datetime.utcnow().year
        if yi < 100:
            yi += 2000
        if not (1 <= di <= 31 and 1 <= mi <= 12):
            return ""
        return f"{di:02d}/{mi:02d}/{yi}"
    except (ValueError, TypeError):
        return ""


def extract_promo_dates(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = _RANGE.search(text)
    if m:
        g = m.groups()
        start = _norm(g[0], g[1], g[2])
        end = _norm(g[3], g[4], g[5])
        if start or end:
            return start, end
    start = end = ""
    ms = _START.search(text)
    if ms:
        start = _norm(ms.group(1), ms.group(2), ms.group(3))
    me = _END.search(text)
    if me:
        end = _norm(me.group(1), me.group(2), me.group(3))
    return start, end
