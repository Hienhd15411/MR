from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CRAWL_WINDOW_DAYS = int(os.getenv("CRAWL_WINDOW_DAYS", "7"))

SOURCES_YAML = ROOT / "src" / "config" / "sources.yaml"
LOG_DIR = ROOT / "logs"
CACHE_DIR = ROOT / ".cache"
TMP_DIR = ROOT / "tmp"

for d in (LOG_DIR, CACHE_DIR, TMP_DIR):
    d.mkdir(exist_ok=True)


def google_sheets_id() -> str:
    sid = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    if not sid:
        raise RuntimeError("GOOGLE_SHEETS_ID is not set")
    return sid


def google_credentials_json() -> str:
    """Return service-account JSON as string.

    Prefer GOOGLE_APPLICATION_CREDENTIALS (file path) for local dev,
    fall back to inline GOOGLE_SHEETS_CREDENTIALS_JSON for CI.
    """
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path:
        return Path(path).read_text(encoding="utf-8")
    inline = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
    if inline:
        return inline
    raise RuntimeError(
        "Set GOOGLE_APPLICATION_CREDENTIALS (file path) or "
        "GOOGLE_SHEETS_CREDENTIALS_JSON (inline JSON)."
    )
