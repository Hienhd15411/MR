"""Bridge between Claude Code (manual AI processing) and Google Sheets.

Two modes:

    python scripts/process_with_ai.py --export
        → Reads `raw_data` from Sheets, picks rows with status='new',
          writes them to tmp/to_process.json.

    python scripts/process_with_ai.py --apply
        → Reads tmp/processed.json (produced by Claude Code via the
          .claude/agents/ai-processor.md agent), appends to `final_data`,
          and updates raw_data status to 'processed' (or 'filtered_out'
          when final_score < 3).

This file MUST NOT import anthropic / openai / any AI SDK. The intelligence
lives in Claude Code which the user drives manually.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from src.config.settings import TMP_DIR  # noqa: E402
from src.storage.schema import FINAL_EXTRA_HEADERS  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

EXPORT_PATH = TMP_DIR / "to_process.json"
PROCESSED_PATH = TMP_DIR / "processed.json"


def cmd_export() -> int:
    from src.storage.sheets import SheetsClient  # lazy import

    client = SheetsClient.from_env()
    rows = client.fetch_new_raw_rows()
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    logger.info("Exported {} new rows → {}", len(rows), EXPORT_PATH)
    print(f"Wrote {len(rows)} rows to {EXPORT_PATH}")
    print("Next: open Claude Code, follow .claude/agents/ai-processor.md,")
    print(f"      and save the result as {PROCESSED_PATH}.")
    return 0


_VALID_VERTICALS = {
    "AI", "Chat", "E-commerce", "Travel",
    "Ride/Food Delivery", "E-wallet", "Ticket",
}
_VALID_SIGNAL_LEVELS = {"1", "2", "3", "4", "5",
                        "Low", "Medium", "High", "Strong"}


def _validate_processed(rows: list[dict]) -> list[str]:
    errs: list[str] = []
    required = ["id"] + FINAL_EXTRA_HEADERS
    for i, r in enumerate(rows):
        for k in required:
            if k not in r:
                errs.append(f"row {i}: missing field {k!r}")
        rv = r.get("related_vertical", "")
        if rv and rv not in _VALID_VERTICALS:
            errs.append(
                f"row {i}: related_vertical {rv!r} not in "
                f"{sorted(_VALID_VERTICALS)}"
            )
        sig = str(r.get("signal_level", "")).strip()
        if sig and sig not in _VALID_SIGNAL_LEVELS:
            errs.append(
                f"row {i}: signal_level {sig!r} not in "
                f"{sorted(_VALID_SIGNAL_LEVELS)}"
            )
    return errs


def cmd_apply(processed_path: Path = PROCESSED_PATH, dry_run: bool = False) -> int:
    if not processed_path.exists():
        print(f"Not found: {processed_path}", file=sys.stderr)
        return 2
    rows = json.loads(processed_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("processed.json must be a JSON array", file=sys.stderr)
        return 2
    errs = _validate_processed(rows)
    if errs:
        print("Validation failed:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 3
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("ai_processed_at", now)
        if isinstance(r.get("mentioned_players"), list):
            r["mentioned_players"] = ", ".join(r["mentioned_players"])

    ids = [r["id"] for r in rows if r.get("id")]

    if dry_run:
        print(f"[dry-run] would append {len(rows)} rows to final_data")
        print(f"[dry-run] would mark {len(ids)} as processed")
        return 0

    from src.storage.sheets import SheetsClient

    client = SheetsClient.from_env()
    client.append_final(rows)
    client.mark_status(ids, "processed")
    logger.info("Applied {} rows", len(rows))
    print(f"Applied {len(rows)} rows.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true",
                   help=f"Export new raw_data rows to {EXPORT_PATH}")
    g.add_argument("--apply", action="store_true",
                   help=f"Apply {PROCESSED_PATH} to final_data + update statuses")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate only; do not write to Sheets")
    parser.add_argument("--input", type=Path, default=PROCESSED_PATH,
                        help="Path to processed.json (default: tmp/processed.json)")
    args = parser.parse_args(argv)

    setup_logger()
    if args.export:
        return cmd_export()
    return cmd_apply(processed_path=args.input, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
