# Hienhd Market Watch

Auto-crawl + AI-assisted weekly Market Watch report.

- **Auto crawl** runs in GitHub Actions (Sunday 23:00 UTC = Monday 06:00 ICT)
  and writes raw articles to the `raw_data` tab of a Google Sheet (and/or
  `output/raw_data.xlsx` + `output/raw_data.md` for review).
- **AI processing** is done manually through Claude Code (Max plan). The agent
  prompt lives at `.claude/agents/ai-processor.md`. **No Anthropic API/SDK
  is used in this codebase.**

## Architecture

```
┌──────────── GitHub Actions (weekly cron) ────────────┐
│ src/main.py                                          │
│   ├─ build_crawlers_from_yaml(sources.yaml)          │
│   ├─ asyncio.gather (Semaphore=5)                    │
│   ├─ apply_filter(categories.yaml)                   │
│   └─ write to: Google Sheets / xlsx / markdown       │
└──────────────────────────────────────────────────────┘
                       │
                       ▼  (raw_data tab, status='new')
┌──────────────── Manual on Monday morning ────────────┐
│ scripts/process_with_ai.py --export                  │
│   → tmp/to_process.json                              │
│ Claude Code (.claude/agents/ai-processor.md)         │
│   → tmp/processed.json (scoring + summary + title)   │
│ scripts/process_with_ai.py --apply                   │
│   → final_data tab + status update                   │
└──────────────────────────────────────────────────────┘
```

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium     # only needed for MoMo / Grab
cp .env.example .env
# Set GOOGLE_SHEETS_ID and either GOOGLE_APPLICATION_CREDENTIALS (file path)
# or GOOGLE_SHEETS_CREDENTIALS_JSON (inline JSON).

# Crawl + write Excel + Markdown (no Sheets needed)
python -m src.main --excel output/raw_data.xlsx --markdown output/raw_data.md

# Crawl + write directly to Google Sheets
python -m src.main --sheet

# Demo without external network (uses tests/fixtures/vnexpress_rss.xml)
PYTHONPATH=. python scripts/demo_with_fixture.py

# Run tests
pytest -q
```

## Sources

22 sources are declared in `src/config/sources.yaml`:

- **News (RSS, 21):** VnExpress (×2), Tuổi Trẻ (×2), Thanh Niên, CafeF (×2),
  CafeBiz, The Leader, Nhịp Cầu Đầu Tư, VietnamNet ICT, Genk, VIR, The Saigon
  Times, Báo Đầu Tư, TechCrunch, The Verge, Bloomberg Tech, Reuters Tech (via
  Google News), Tech in Asia, KrAsia, Rest of World, e27.
- **Players (Playwright + httpx fallback, 2):** MoMo Newsroom, Grab VN Blog.

Adding a new RSS source = 1 YAML entry. Adding a Playwright source = 1 class
plus 1 YAML entry referencing it via `module: pkg.mod:Class`.

## Filter / categorisation

`src/pipeline/filter.py` reads `src/config/categories.yaml` and:

1. Tags articles with `pre_category` (e.g. `AI/AI agents`,
   `Fintech/E-wallet`, `Marketing/User acquisition`).
2. If a Player keyword (MoMo, Grab) hits, reclassifies the article as
   `players_movement` and fills `player`.
3. Articles with no keyword hit are kept but flagged `status=filtered_out`.

Word boundaries are enforced so `AI` does not match `AirAsia`. Both accented
and accent-stripped Vietnamese keywords are matched.

## AI processing (manual, via Claude Code)

```bash
# 1) Pull new rows from raw_data into a JSON file
python scripts/process_with_ai.py --export       # → tmp/to_process.json

# 2) Open Claude Code and follow .claude/agents/ai-processor.md
#    to produce tmp/processed.json (scoring, summary, normalised title).

# 3) Validate without writing to Sheets
python scripts/process_with_ai.py --apply --dry-run

# 4) Apply: appends to final_data tab and updates raw_data.status
python scripts/process_with_ai.py --apply
```

The validator enforces score ranges [1..5] and `final_score == impact*0.6 +
relevance*0.4 ± 0.01`. Rows with `final_score < 3` are auto-tagged
`low_priority` (kept for reference, not shown in the report).

## Google Cloud setup

1. Create a project in Google Cloud Console.
2. Enable **Google Sheets API** and **Google Drive API**.
3. Create a Service Account → JSON key → download.
4. Open the target Google Sheet → **Share Editor** with the service account
   email.
5. Copy the Sheet ID from the URL.
6. Set `GOOGLE_SHEETS_ID` and either `GOOGLE_APPLICATION_CREDENTIALS`
   (file path, recommended for local dev) or
   `GOOGLE_SHEETS_CREDENTIALS_JSON` (inline JSON, used by CI).

## GitHub Actions

The workflow at `.github/workflows/crawl.yml`:

- runs on `workflow_dispatch` (manual) and the weekly cron `0 23 * * 0`,
- installs deps + Chromium (cached),
- runs `pytest`,
- crawls 22 sources, applies filter, writes
  `output/raw_data.xlsx` and `output/raw_data.md`,
- uploads `output/` and `logs/` as a 30-day artifact,
- on **manual runs** also commits the two output files back to the branch
  for reviewable diffs.

### Secrets

Set in **Repo → Settings → Secrets and variables → Actions**:

- `GOOGLE_SHEETS_ID` — the Sheet ID from the URL.
- `GOOGLE_SHEETS_CREDENTIALS_JSON` — full service-account JSON (multiline).

These are required only if you pass `--sheet` from the workflow; the default
xlsx + md flow works without them.

## Layout

```
src/
  main.py                       # CLI entry
  config/
    settings.py
    sources.yaml                # 22 sources, declarative
    categories.yaml             # keyword → category mapping
  crawlers/
    base.py                     # BaseCrawler abstract
    rss.py                      # RSSCrawler (BS4 xml)
    factory.py                  # builds crawlers from YAML
    news/vnexpress.py           # named subclass for fixture-based tests
    players/momo.py             # MoMo Newsroom (Playwright fallback)
    players/grab.py             # Grab VN Blog (Playwright fallback)
  pipeline/
    filter.py                   # CategoryClassifier
    orchestrator.py             # asyncio + Semaphore(5)
  storage/
    schema.py                   # SHEET_HEADERS, FINAL_HEADERS (dep-free)
    models.py                   # Pydantic RawArticle
    sheets.py                   # SheetsClient (raw + final + status update)
    excel_sink.py               # openpyxl workbook
    markdown_sink.py            # Markdown preview
  utils/
    logger.py / date_utils.py / anti_bot.py / playwright_fetch.py
scripts/
  process_with_ai.py            # --export / --apply
  demo_with_fixture.py
.claude/agents/ai-processor.md  # the manual AI agent prompt
tests/                          # pytest, RSS fixture, full filter coverage
.github/workflows/crawl.yml
```

## Roadmap

- [x] Iter 1 — skeleton + 1 crawler end-to-end
- [x] Iter 2 — 22 sources via YAML + Playwright players (MoMo/Grab)
- [x] Iter 3 — filter, categories, `process_with_ai.py`, agent prompt,
              `final_data` schema
- [x] Iter 4 — GitHub Actions schedule + Excel/Markdown sinks + full README
- [ ] Phase 3+ — slide PPT generator (out of scope)
- [ ] Phase 4 — QC layer (out of scope)
