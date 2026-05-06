from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from src.pipeline.orchestrator import run_pipeline
from src.utils.logger import setup_logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Market Watch auto-crawl pipeline")
    parser.add_argument(
        "--sheet",
        action="store_true",
        help="Write results to the Google Sheets `raw_data` tab.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Write a Markdown preview of the crawl to this path "
        "(e.g. output/raw_data.md).",
    )
    args = parser.parse_args(argv)

    setup_logger()
    logger.info("Starting Market Watch crawler pipeline")
    summary = run_pipeline(write_to_sheet=args.sheet, markdown_path=args.markdown)
    logger.info("Done. Summary: {}", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
