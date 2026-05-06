from __future__ import annotations

import json
from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from src.config.settings import google_credentials_json, google_sheets_id
from src.storage.models import RawArticle
from src.storage.schema import (
    FINAL_HEADERS,
    FINAL_TAB,
    RAW_TAB,
    SHEET_HEADERS,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, sheet_id: str, creds_json: str):
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(sheet_id)

    @classmethod
    def from_env(cls) -> "SheetsClient":
        return cls(sheet_id=google_sheets_id(), creds_json=google_credentials_json())

    def _ensure_tab(self, name: str, headers: list[str]) -> gspread.Worksheet:
        try:
            ws = self.sh.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.sh.add_worksheet(name, rows=1000, cols=len(headers))
            ws.append_row(headers, value_input_option="RAW")
            return ws
        if not ws.row_values(1):
            ws.append_row(headers, value_input_option="RAW")
        return ws

    def existing_ids(self) -> set[str]:
        ws = self._ensure_tab(RAW_TAB, SHEET_HEADERS)
        col = ws.col_values(1)
        return set(col[1:]) if col else set()

    def append_raw(self, articles: Iterable[RawArticle]) -> int:
        ws = self._ensure_tab(RAW_TAB, SHEET_HEADERS)
        existing = self.existing_ids()
        seen: set[str] = set()
        rows: list[list[str]] = []
        for a in articles:
            if a.id in existing or a.id in seen:
                continue
            seen.add(a.id)
            rows.append(a.to_row())
        if not rows:
            logger.info("No new rows to append to {}", RAW_TAB)
            return 0
        # Single batched write to stay well under the 60 req/min Sheets quota.
        ws.append_rows(rows, value_input_option="RAW")
        logger.info("Appended {} rows to {}", len(rows), RAW_TAB)
        return len(rows)

    # ---- final_data (written by scripts/process_with_ai.py) ----

    def fetch_new_raw_rows(self) -> list[dict]:
        ws = self._ensure_tab(RAW_TAB, SHEET_HEADERS)
        records = ws.get_all_records()
        return [r for r in records if r.get("status") == "new"]

    def append_final(self, processed_rows: list[dict]) -> int:
        ws = self._ensure_tab(FINAL_TAB, FINAL_HEADERS)
        if not processed_rows:
            return 0
        rows = [[str(r.get(h, "")) for h in FINAL_HEADERS] for r in processed_rows]
        ws.append_rows(rows, value_input_option="RAW")
        logger.info("Appended {} rows to {}", len(rows), FINAL_TAB)
        return len(rows)

    def mark_status(self, ids: list[str], status: str) -> int:
        """Update the `status` column for rows whose `id` is in `ids`."""
        if not ids:
            return 0
        ws = self._ensure_tab(RAW_TAB, SHEET_HEADERS)
        all_ids = ws.col_values(1)
        status_col = SHEET_HEADERS.index("status") + 1
        updates = []
        target = set(ids)
        for row_idx, val in enumerate(all_ids, start=1):
            if row_idx == 1:
                continue
            if val in target:
                updates.append({
                    "range": gspread.utils.rowcol_to_a1(row_idx, status_col),
                    "values": [[status]],
                })
        if updates:
            ws.batch_update(updates, value_input_option="RAW")
        return len(updates)
