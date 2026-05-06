"""Sheet schema constants. Kept dependency-free so tests can import without gspread."""

SHEET_HEADERS = [
    "id",
    "crawled_at",
    "source",
    "source_type",
    "url",
    "title_original",
    "content_snippet",
    "published_date",
    "type",
    "pre_category",
    "player",
    "scope",
    "status",
]
RAW_TAB = "raw_data"

# `final_data` tab is written by scripts/process_with_ai.py after Claude Code
# scoring. It extends raw_data with AI-produced columns.
FINAL_EXTRA_HEADERS = [
    "title_normalized",
    "summary",
    "category",
    "sub_category",
    "impact_score",
    "relevance_score",
    "final_score",
    "tags",
    "ai_processed_at",
]
FINAL_HEADERS = SHEET_HEADERS + FINAL_EXTRA_HEADERS
FINAL_TAB = "final_data"
