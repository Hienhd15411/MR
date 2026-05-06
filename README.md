# Hienhd Market Watch

Auto-crawl + AI-assisted weekly Market Watch report.

- **Auto crawl** runs in GitHub Actions (Sunday 23:00 UTC = Monday 06:00 VN) and writes raw articles to the `raw_data` tab of a Google Sheet.
- **AI processing** is done manually through Claude Code (Max plan) — no Anthropic API/SDK is used in this codebase.

## Status

Iteration 1 (skeleton) — VnExpress so-hoa end-to-end via RSS, Pydantic models, Sheets client, tests.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium       # used in later iterations
cp .env.example .env
# Fill GOOGLE_SHEETS_ID and either GOOGLE_APPLICATION_CREDENTIALS (file path)
# or GOOGLE_SHEETS_CREDENTIALS_JSON (inline JSON)

# Crawl + write Excel workbook (raw_data + summary sheets)
python -m src.main --excel output/raw_data.xlsx

# Crawl + write a Markdown preview
python -m src.main --markdown output/raw_data.md

# Crawl + write to Google Sheets `raw_data`
python -m src.main --sheet

# Combine any of them
python -m src.main --excel output/raw_data.xlsx --markdown output/raw_data.md

# Demo without external network (uses tests/fixtures/vnexpress_rss.xml)
PYTHONPATH=. python scripts/demo_with_fixture.py

# Run tests
pytest -q
```

## Google Cloud Service Account setup

1. Create a project in Google Cloud Console.
2. Enable **Google Sheets API** and **Google Drive API**.
3. Create a Service Account, then a JSON key. Download the key file.
4. Open the target Google Sheet and **Share** it with the service account email (Editor).
5. Copy the Sheet ID from the URL.
6. Set `GOOGLE_SHEETS_ID` and either `GOOGLE_APPLICATION_CREDENTIALS` (path to JSON) or paste the JSON into `GOOGLE_SHEETS_CREDENTIALS_JSON`.

## GitHub Actions secrets (used from Iteration 4)

- `GOOGLE_SHEETS_ID`
- `GOOGLE_SHEETS_CREDENTIALS_JSON` — full JSON pasted as a multiline secret.

## Layout

```
src/
  main.py                 # CLI entry
  config/                 # settings + sources.yaml
  crawlers/
    base.py               # BaseCrawler abstract
    rss.py                # RSSCrawler base
    news/vnexpress.py     # VnExpress so-hoa (Iter 1)
  pipeline/orchestrator.py
  storage/
    models.py             # Pydantic RawArticle
    sheets.py             # SheetsClient
  utils/                  # logger, date_utils, anti_bot
tests/                    # pytest, with RSS fixture
```

## Roadmap

- [x] Iter 1: skeleton + 1 crawler end-to-end
- [ ] Iter 2: remaining 19 news + MoMo & Grab + Playwright fallback
- [ ] Iter 3: filter, categories, `scripts/process_with_ai.py`, AI agent prompt
- [ ] Iter 4: GitHub Actions schedule + full README
