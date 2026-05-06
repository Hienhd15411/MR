# Iteration 1 — Review

Branch: `claude/market-watch-crawler-Bhj7D`
Mục tiêu: skeleton + 1 crawler (VnExpress so-hoa) chạy end-to-end → ghi Google Sheet `raw_data`.

---

## 1. Quyết định thiết kế đã chốt

| Quyết định | Lý do |
|---|---|
| **RSS-first** thay vì HTML | Ổn định gấp ~10x, ít bị block, ít vỡ khi báo đổi layout. Dùng `BaseCrawler` + `RSSCrawler` subclass; HTML/Playwright chỉ làm fallback ở Iter 2 cho nguồn không có RSS (MoMo, Grab, Bloomberg…). |
| **`dateparser`** trong stack | Xử lý được cả "Thứ Hai, 6/5/2026, 14:30 (GMT+7)" và RFC822 từ RSS. Centralize ở `utils/date_utils.py`, mọi datetime đều UTC-aware. |
| **Dedupe theo `id = sha256(url)[:16]`** | Idempotent — rerun không sinh duplicate. Sheets client đọc cột A trước khi append. |
| **Batched `append_rows` 1 lần cuối** | Tránh quota Sheets 60 write/phút. Toàn bộ pipeline ghi đúng 1 request. |
| **`schema.py` tách khỏi `sheets.py`** | Test models không phải import gspread (heavy + cryptography deps). |
| **asyncio Semaphore(5)** | 22 crawler chạy parallel có giới hạn — không hammer 1 site. |
| **Fail-soft mọi tầng** | 1 source crash không làm crash pipeline. Log warning + skip. |
| **`.env` ưu tiên file path** cho creds local, inline JSON cho CI | Tránh khổ với multiline JSON ở local; CI dùng GitHub Secret multiline. |

---

## 2. Cấu trúc repo

```
hienhd-market-watch/
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── main.py                       # CLI entry, --no-sheet để debug
│   ├── config/
│   │   ├── settings.py               # load .env, paths, helpers
│   │   └── sources.yaml              # Iter 1 chỉ có vnexpress_sohoa
│   ├── crawlers/
│   │   ├── base.py                   # BaseCrawler abstract + fetch fail-soft
│   │   ├── rss.py                    # RSSCrawler + parse_rss (BS4 xml)
│   │   ├── news/vnexpress.py
│   │   └── players/                  # placeholder cho Iter 2
│   ├── pipeline/orchestrator.py      # asyncio.gather + Semaphore(5)
│   ├── storage/
│   │   ├── models.py                 # Pydantic RawArticle + enums
│   │   ├── schema.py                 # SHEET_HEADERS, RAW_TAB (dep-free)
│   │   └── sheets.py                 # SheetsClient (batched append, dedupe)
│   └── utils/
│       ├── anti_bot.py               # UA rotate + polite_delay 2-5s
│       ├── date_utils.py             # parse_date / parse_vn_date / within_window
│       └── logger.py                 # loguru → stderr + logs/run-YYYYMMDD.log
└── tests/                            # 12 tests, all passing
    ├── fixtures/vnexpress_rss.xml
    ├── test_models.py
    ├── test_date_utils.py
    └── test_vnexpress_crawler.py
```

---

## 3. Schema `raw_data`

13 cột — alignment giữa `RawArticle.to_row()` và `SHEET_HEADERS` được test_models bảo vệ:

```
id | crawled_at | source | source_type | url | title_original
   | content_snippet | published_date | type | pre_category
   | player | scope | status
```

- `id` = `sha256(url)[:16]` → dedupe key.
- `crawled_at`, `published_date` = ISO8601 UTC.
- `type` ∈ `market_pulse|players_movement`.
- `source_type` ∈ `news|website`.
- `scope` ∈ `domestic|international`.
- `status` ∈ `new|processed|filtered_out` — Iter 1 luôn ghi `new`.

---

## 4. Test coverage Iter 1

12/12 pass:

- `test_models.py` — make_id deterministic, snippet truncate 500 chars, empty title rejected, default status, row-length khớp header.
- `test_date_utils.py` — RFC822 (`Mon, 05 May 2026 03:00:00 +0700` → 04 May 20:00 UTC), VN tự do, garbage → None, window filter.
- `test_vnexpress_crawler.py` — parse RSS fixture (3 items), end-to-end với fake_fetch, window filter loại bài 2024.

Chạy lại: `pytest -q`.

---

## 5. Risk / điểm cần xem

### Đã xử lý
- ✅ Sheets quota → batched write
- ✅ Date đa ngôn ngữ → dateparser
- ✅ Empty title → ValidationError
- ✅ Source crash → fail-soft, không crash pipeline
- ✅ Rerun duplicate → dedup by ID

### Còn pending (Iter 2+)
- ⚠️ Bloomberg / Reuters / Saigon Times paywall + Cloudflare → có thể phải bỏ hoặc chỉ scan headline
- ⚠️ MoMo/Grab newsroom có thể là SPA → Playwright bắt buộc
- ⚠️ Fuzzy dedupe cross-source (cùng tin nhiều báo) → để Iter 3 xử ở filter hoặc đẩy sang AI step
- ⚠️ Keyword filter category (Iter 3) cần word boundary regex để tránh "AI" match "AirAsia"
- ⚠️ Playwright trên Actions cần cache `~/.cache/ms-playwright` (Iter 4)

---

## 6. Setup môi trường còn lại (anh làm trước Iter 2)

1. **Google Cloud Console** → tạo project, enable Sheets API + Drive API.
2. Tạo **Service Account** → tạo JSON key, tải về.
3. Tạo Google Sheet "Market Watch Data", **Share Editor** cho email service account.
4. Copy Sheet ID từ URL.
5. Local: `cp .env.example .env`, set `GOOGLE_SHEETS_ID` + `GOOGLE_APPLICATION_CREDENTIALS=/abs/path/key.json`.
6. Smoke test:
   ```bash
   pip install -r requirements.txt
   python -m src.main --no-sheet     # crawl-only
   python -m src.main                # crawl + write
   ```

GitHub Secrets có thể đợi Iter 4 (lúc setup workflow):
- `GOOGLE_SHEETS_ID`
- `GOOGLE_SHEETS_CREDENTIALS_JSON` (paste full JSON multiline)

---

## 7. Câu hỏi cho anh trước Iter 2

1. **Playwright**: anh muốn em wrap thành 1 utility `fetch_with_fallback(url)` (httpx → Playwright khi 403/429) hay tách `PlaywrightCrawler` riêng cho MoMo/Grab?
2. **Bloomberg/Reuters**: nếu Cloudflare chặn cả Playwright headless → anh OK skip 2 nguồn này, hay muốn thay bằng Google News RSS với keyword query?
3. **Sources.yaml**: anh muốn em define toàn bộ 22 nguồn declarative trong YAML và auto-load (1 class generic per type), hay giữ 1 file Python per source (rõ ràng hơn nhưng nhiều file)?

→ Em nghiêng về: (1) tách `PlaywrightCrawler` riêng, (2) Google News RSS fallback, (3) declarative YAML cho RSS sources + Python class cho HTML/Playwright sources (hybrid).

---

## 8. Definition of Done — Iter 1 ✅

- [x] Repo structure đúng layout
- [x] `python -m src.main` chạy được, log số bài crawl, ghi Sheet
- [x] Rerun không tạo duplicate
- [x] `pytest` pass
- [x] README quick-start
- [x] Push lên branch `claude/market-watch-crawler-Bhj7D`
