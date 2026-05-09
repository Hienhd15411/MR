"""Sheet schema constants. Kept dependency-free so tests can import without gspread.

Aligned 1:1 with the user's MR26001 MarketWatch Database Excel.
"""

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

# Final database columns mirror references/MR26001_MarketWatch_Database
# (sheet `Database_clean`). Each AI-processed row must populate every
# field below. Validators in scripts/process_with_ai.py enforce this.
FINAL_EXTRA_HEADERS = [
    # Provenance (carried from raw_data)
    "week",
    "source_name",
    "title_raw",
    "publish_date",

    # Coding step (Bước 2-5 in the Excel)
    "topic_group",          # Market Pulse | Players Movement
    "sub_topic_group",      # Quốc tế / Trung quốc / SEA / Trong nước OR <Player>
    "category",             # Political/Economic/Social/Technology/Legal | Product/Feature/Marketing/Partnership/CSR/Strategy
    "subcategory",          # AI/Gen AI, Funding/Investment, …
    "merged_category",      # "{category} | {subcategory}" — printed tag
    "related_vertical",     # AI / MXH-Chat / E-Commerce / Ride-Food Delivery / Fintech-E-wallet / Travel-Ticket / Smart city

    # Editorial output (Bước 2-3 in the Excel)
    "title_normalized",     # ≤ 18 words, Vietnamese
    "summary",              # 3-4 bullets joined by \n

    # Time-bound campaigns / launches
    "start_date",           # DD/MM/YYYY or empty
    "end_date",

    # Free tags
    "tags",

    # Grading (Bước Updating-Scoring in the Excel)
    "R1",                   # Strategic relevance     (1-5)  weight 0.40
    "R2",                   # Market impact           (1-5)  weight 0.25
    "R3",                   # Competitive intelligence (1-5) weight 0.20
    "R4",                   # Technology inflection   (1-5)  weight 0.15
    "signal_score",         # 1-5 weighted average
    "signal_level",         # 1 Noise / 2 Minor / 3 Market / 4 Strategic / 5 Disruption

    "ai_processed_at",
]
FINAL_HEADERS = SHEET_HEADERS + FINAL_EXTRA_HEADERS
FINAL_TAB = "final_data"


# Score → level mapping (from the Grading sheet)
SIGNAL_LEVEL_BANDS = [
    (4.21, 5.00, "5 - Industry disruption"),
    (3.41, 4.20, "4 - Strategic shift"),
    (2.51, 3.40, "3 - Market signal"),
    (1.61, 2.50, "2 - Minor signal"),
    (0.00, 1.60, "1 - Noise"),
]


def signal_level_for(score: float) -> str:
    for lo, hi, label in SIGNAL_LEVEL_BANDS:
        if lo <= score <= hi:
            return label
    return "1 - Noise"


def compute_signal_score(r1: float, r2: float, r3: float, r4: float) -> float:
    """Excel formula: R1*0.4 + R2*0.25 + R3*0.2 + R4*0.15."""
    return round(r1 * 0.40 + r2 * 0.25 + r3 * 0.20 + r4 * 0.15, 2)
