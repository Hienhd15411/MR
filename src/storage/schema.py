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
# Schema aligned with the user's manual MarketWatch Excel database:
# fields produced by the Phase-2 AI step and written to `final_data` tab.
#
# Reference:
#   topic_group / sub_topic_group  — top-level taxonomy from Coding sheet
#   category / subcategory          — second-level taxonomy
#   related_vertical                — one of the 7 verticals (AI, Chat,
#                                     E-commerce, Travel, Ride/Food,
#                                     E-wallet, Ticket)
#   start_date / end_date           — for campaigns / time-bound events
#                                     (otherwise empty); separate fields
#   signal_level                    — replaces impact*0.6 + relevance*0.4
#   mentioned_players               — comma-separated tracked + adjacent
#                                     players surfaced in the article
#   week                            — ISO week tag, e.g. "W18-26"
FINAL_EXTRA_HEADERS = [
    "week",
    "topic_group",
    "sub_topic_group",
    "category",
    "subcategory",
    "related_vertical",
    "title_normalized",
    "summary",
    "start_date",
    "end_date",
    "signal_level",
    "mentioned_players",
    "ai_processed_at",
]
FINAL_HEADERS = SHEET_HEADERS + FINAL_EXTRA_HEADERS
FINAL_TAB = "final_data"
