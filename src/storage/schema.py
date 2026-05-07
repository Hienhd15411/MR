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
# Schema aligned with the Weekly Market Watch report template:
#   - `summary` carries 3-4 markdown bullets (\n-separated) following the
#     What / Numbers / Implication pattern from the template.
#   - `topic_lens` + `topic_sub` produce the article-level tag (e.g.
#     "Technology | AI/ Gen AI", "Legal | Fintech/ Wallet"). Independent
#     of the business `category` (AI / Fintech / TMĐT / …).
#   - `campaign_period` is filled for Players Movement Marketing items
#     (e.g. "24/04 – 05/05") and left empty otherwise.
FINAL_EXTRA_HEADERS = [
    "title_normalized",
    "summary",
    "category",
    "sub_category",
    "topic_lens",
    "topic_sub",
    "campaign_period",
    "impact_score",
    "relevance_score",
    "final_score",
    "tags",
    "ai_processed_at",
]
FINAL_HEADERS = SHEET_HEADERS + FINAL_EXTRA_HEADERS
FINAL_TAB = "final_data"
