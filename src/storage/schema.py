"""Output schema — Market Watch Crawler Instructions v2, Section 5.

Sheet "Database" — 22 columns, fixed order. Columns 12/13/14/15/16/22
are HUMAN in Round 2 (left blank or rough by the crawler). Round-1
auto columns are filled by the pipeline.
"""

# raw_data tab (legacy local sink) keeps the old 13-col preview shape
SHEET_HEADERS = [
    "id", "crawled_at", "source", "source_type", "url",
    "title_original", "content_snippet", "published_date", "type",
    "pre_category", "player", "scope", "status",
]
RAW_TAB = "raw_data"

# Section 5 — Sheet "Database" (22 cols, exact order)
DATABASE_HEADERS = [
    "id",                # 1  auto
    "url",               # 2  auto
    "hyperlink",         # 3  auto (= title_normalized when present)
    "source_name",       # 4  auto
    "signal_level",      # 5  auto (compute)
    "week",              # 6  auto
    "crawl_date",        # 7  auto
    "title_raw",         # 8  auto
    "publish_date",      # 9  auto
    "topic_group",       # 10 auto (Sec 2.6)
    "sub_topic_group",   # 11 auto (Sec 2.5)
    "category",          # 12 HUMAN
    "subcategory",       # 13 HUMAN
    "merged_category",   # 14 auto (= cat | subcat)
    "title_normalized",  # 15 HUMAN (rough = title_raw)
    "summary",           # 16 HUMAN (rough = snippet)
    "start_date",        # 17 optional auto
    "end_date",          # 18 optional auto
    "R1",                # 19 auto basic
    "R2",                # 20 auto basic
    "signal_score",      # 21 auto compute
    "related_vertical",  # 22 HUMAN
    "source_site",       # 23 auto — human-readable publisher/site
]
DATABASE_TAB = "Database"

DISCARDED_HEADERS = [
    "url", "source_name", "source_site", "title_raw", "publish_date",
    "discard_reason", "matched_keywords", "review_flag",
]
DISCARDED_TAB = "Discarded"

AUDIT_HEADERS = [
    "crawl_start_time", "crawl_end_time", "source_name",
    "articles_fetched", "articles_kept", "articles_discarded",
    "articles_flagged", "errors",
]
AUDIT_TAB = "Audit_Log"

# Back-compat aliases (older imports)
FINAL_HEADERS = DATABASE_HEADERS
FINAL_TAB = DATABASE_TAB
FINAL_EXTRA_HEADERS = DATABASE_HEADERS


def signal_level_for(score: float) -> str:
    from src.pipeline.scoring import signal_level_for as _s
    return _s(score)
