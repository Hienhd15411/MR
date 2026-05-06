from __future__ import annotations

import argparse
import sys

from loguru import logger

from src.pipeline.orchestrator import run_pipeline
from src.utils.logger import setup_logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Market Watch auto-crawl pipeline")
    parser.add_argument(
        "--no-sheet",
        action="store_true",
        help="Crawl only, skip writing to Google Sheets (useful for local debug).",
    )
    args = parser.parse_args(argv)

    setup_logger()
    logger.info("Starting Market Watch crawler pipeline")
    summary = run_pipeline(write_to_sheet=not args.no_sheet)
    logger.info("Done. Summary: {}", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
