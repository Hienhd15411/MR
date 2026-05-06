from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ArticleType(str, Enum):
    MARKET_PULSE = "market_pulse"
    PLAYERS_MOVEMENT = "players_movement"


class SourceType(str, Enum):
    NEWS = "news"
    WEBSITE = "website"


class Scope(str, Enum):
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"


class Status(str, Enum):
    NEW = "new"
    PROCESSED = "processed"
    FILTERED_OUT = "filtered_out"


class RawArticle(BaseModel):
    """One row in the `raw_data` Google Sheet tab."""

    id: str
    crawled_at: datetime
    source: str
    source_type: SourceType
    url: str
    title_original: str
    content_snippet: str = Field(default="", max_length=500)
    published_date: Optional[datetime] = None
    type: ArticleType
    pre_category: Optional[str] = None
    player: Optional[str] = None
    scope: Scope
    status: Status = Status.NEW

    @field_validator("content_snippet", mode="before")
    @classmethod
    def _truncate_snippet(cls, v: Optional[str]) -> str:
        if not v:
            return ""
        return v[:500]

    @field_validator("title_original")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("title_original must not be empty")
        return v

    @classmethod
    def make_id(cls, url: str) -> str:
        return sha256(url.encode("utf-8")).hexdigest()[:16]

    def to_row(self) -> list[str]:
        """Order MUST stay aligned with SHEET_HEADERS in storage.sheets."""
        return [
            self.id,
            self.crawled_at.isoformat(),
            self.source,
            self.source_type.value,
            self.url,
            self.title_original,
            self.content_snippet,
            self.published_date.isoformat() if self.published_date else "",
            self.type.value,
            self.pre_category or "",
            self.player or "",
            self.scope.value,
            self.status.value,
        ]
