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


_VALID_TOPIC_LENS = {"Legal", "Technology", "Economic"}


def _validate_processed(rows: list[dict]) -> list[str]:
    errs: list[str] = []
    required = ["id"] + FINAL_EXTRA_HEADERS
    for i, r in enumerate(rows):
        for k in required:
            if k not in r:
                errs.append(f"row {i}: missing field {k!r}")
        if r.get("topic_lens") and r["topic_lens"] not in _VALID_TOPIC_LENS:
            errs.append(
                f"row {i}: topic_lens {r['topic_lens']!r} not in "
                f"{sorted(_VALID_TOPIC_LENS)}"
            )
        try:
            impact = float(r.get("impact_score", 0))
            relevance = float(r.get("relevance_score", 0))
            final = float(r.get("final_score", 0))
        except (TypeError, ValueError):
            errs.append(f"row {i}: scores must be numeric")
            continue
        if not 1 <= impact <= 5:
            errs.append(f"row {i}: impact_score out of [1..5]")
        if not 1 <= relevance <= 5:
            errs.append(f"row {i}: relevance_score out of [1..5]")
        expected = round(impact * 0.6 + relevance * 0.4, 2)
        if abs(expected - round(final, 2)) > 0.01:
            errs.append(
                f"row {i}: final_score {final} != impact*0.6 + relevance*0.4 "
                f"(expected {expected})"
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
        if isinstance(r.get("tags"), list):
            r["tags"] = ", ".join(r["tags"])
        score = float(r.get("final_score", 0))
        if score < 3 and "low_priority" not in str(r.get("tags", "")):
            r["tags"] = (str(r.get("tags", "")).strip(", ")
                          + (", low_priority" if r.get("tags") else "low_priority"))
    # Per spec: `final_score < 3 → tag low_priority (KHÔNG xoá, để tham khảo)`.
    # All AI-processed rows get status='processed' regardless of score; the
    # low_priority tag is the only differentiator for downstream filtering.
    ids = [r["id"] for r in rows if r.get("id")]
    low_count = sum(1 for r in rows if float(r.get("final_score", 0)) < 3)

    if dry_run:
        print(f"[dry-run] would append {len(rows)} rows to final_data")
        print(f"[dry-run] would mark {len(ids)} as processed "
              f"({low_count} tagged low_priority)")
        return 0

    from src.storage.sheets import SheetsClient

    client = SheetsClient.from_env()
    client.append_final(rows)
    client.mark_status(ids, "processed")
    logger.info("Applied {} rows ({} tagged low_priority)", len(rows), low_count)
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
