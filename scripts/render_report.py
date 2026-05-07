"""Render a Weekly Market Watch markdown report from `tmp/processed.json`.

Produces a structured markdown that mirrors the PowerPoint template:

  - Cover summary (top headlines per category)
  - Section "Bản tin theo ngành" (5-column matrix: Ride / TMĐT / Fintech / MXH / AI)
  - 1.1 Market Pulse | Thị trường thế giới
  - 1.2 Market Pulse | Thị trường trong nước
  - 2.x Players Movement | <Player> for each of MoMo / Zalo / Grab / Shopee / TikTokShop

Usage:
    python scripts/render_report.py                        # default tmp/processed.json
    python scripts/render_report.py --input my.json --output report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_INPUT = ROOT / "tmp" / "processed.json"
DEFAULT_OUTPUT = ROOT / "output" / "weekly_report.md"

# Section ordering follows the template.
PLAYER_ORDER = ["MoMo", "Zalo", "Grab", "Shopee", "TikTokShop"]
MP_BUCKETS = [
    ("Ride/Food delivery", "Ride-hailing / Delivery"),
    ("TMĐT", "TMĐT"),
    ("Fintech/E-wallet", "Fintech / Đầu tư"),
    ("Chat", "MXH / Chat / Giải trí"),
    ("AI", "AI"),
]


def _is_pm(row: dict) -> bool:
    return (row.get("type") == "players_movement"
            or row.get("player") in PLAYER_ORDER)


def _is_intl(row: dict) -> bool:
    return row.get("scope") == "international"


def _bucket_for_mp(row: dict) -> str:
    cat = row.get("category", "") or row.get("pre_category", "")
    cat = cat.split("/")[0].strip() if cat else ""
    for key, _ in MP_BUCKETS:
        if cat == key.split("/")[0].strip():
            return key
        if cat in key:
            return key
    return cat or "Khác"


def _topic_tag(row: dict) -> str:
    lens = row.get("topic_lens", "")
    sub = row.get("topic_sub", "")
    if lens and sub:
        return f"{lens} | {sub}"
    return lens or sub


def _render_article(row: dict, lines: list[str]) -> None:
    title = row.get("title_normalized") or row.get("title_original", "")
    url = row.get("url", "")
    tag = _topic_tag(row)
    period = row.get("campaign_period", "")
    score = row.get("final_score", "")

    head = f"### {title}"
    if tag:
        head += f"  \n*{tag}*"
    lines.append(head)
    if period:
        lines.append(f"**Thời gian:** {period}")
    summary = row.get("summary", "").strip()
    if summary:
        # Summary may be either bullet text or plain. Normalise to bullets.
        for line in summary.splitlines():
            line = line.rstrip()
            if not line:
                continue
            if not line.lstrip().startswith(("•", "-", "*")):
                line = "• " + line
            lines.append(line)
    if url:
        lines.append(f"[Read more]({url}) · score `{score}`")
    lines.append("")


def render(rows: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [
        "# Weekly Market Watch",
        "",
        "> *From Market Signals to Strategic Insights*",
        "",
        f"- Generated: **{now}**",
        f"- Articles: **{len(rows)}**",
        "",
    ]

    # ---- Bản tin theo ngành (matrix preview) ----
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    pm_rows: list[dict] = []
    for r in rows:
        if _is_pm(r):
            pm_rows.append(r)
            continue
        by_bucket[_bucket_for_mp(r)].append(r)

    lines.append("## Bản tin theo ngành")
    lines.append("")
    lines.append("| " + " | ".join(label for _, label in MP_BUCKETS) + " |")
    lines.append("|" + " --- |" * len(MP_BUCKETS))
    max_rows = max((len(by_bucket.get(k, [])) for k, _ in MP_BUCKETS), default=0)
    for i in range(min(max_rows, 6)):
        cells = []
        for key, _ in MP_BUCKETS:
            items = by_bucket.get(key, [])
            cells.append(items[i].get("title_normalized", "") if i < len(items) else "")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # ---- 1.1 MP World ----
    intl = [r for r in rows if not _is_pm(r) and _is_intl(r)]
    intl.sort(key=lambda r: -float(r.get("final_score") or 0))
    lines.append("## 1.1 Market Pulse | Thị trường thế giới")
    lines.append("")
    if not intl:
        lines.append("_Không có tin thuộc nhóm này tuần qua._")
        lines.append("")
    for r in intl:
        _render_article(r, lines)

    # ---- 1.2 MP Vietnam ----
    domestic = [r for r in rows if not _is_pm(r) and not _is_intl(r)]
    domestic.sort(key=lambda r: -float(r.get("final_score") or 0))
    lines.append("## 1.2 Market Pulse | Thị trường trong nước")
    lines.append("")
    if not domestic:
        lines.append("_Không có tin thuộc nhóm này tuần qua._")
        lines.append("")
    for r in domestic:
        _render_article(r, lines)

    # ---- 2.x Players Movement ----
    pm_by_player: dict[str, list[dict]] = defaultdict(list)
    for r in pm_rows:
        pm_by_player[r.get("player") or "Khác"].append(r)

    for idx, player in enumerate(PLAYER_ORDER, start=1):
        items = pm_by_player.get(player, [])
        lines.append(f"## 2.{idx} Players Movement | {player}")
        lines.append("")
        if not items:
            lines.append("_Không có tin tuần qua._")
            lines.append("")
            continue
        items.sort(key=lambda r: -float(r.get("final_score") or 0))
        for r in items:
            _render_article(r, lines)

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="processed.json (default: tmp/processed.json)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="output markdown path")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Not found: {args.input}", file=sys.stderr)
        return 2
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("Input must be a JSON array", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} articles to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
