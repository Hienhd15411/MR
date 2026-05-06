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
