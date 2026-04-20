from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    source: str
    title: str
    summary: str
    url: str | None = None
    published_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0


class ExchangeRate(BaseModel):
    base: str = "CNY"
    usd_cny: Decimal
    eur_cny: Decimal
    as_of: datetime
    stale: bool = False


class DailyDigest(BaseModel):
    title: str
    date_text: str
    lunar_text: str
    exchange_rate: ExchangeRate
    news_items: list[NewsItem]
    markdown: str | None = None
    html: str | None = None


class DraftArticle(BaseModel):
    title: str
    author: str
    digest: str
    content: str
    thumb_media_id: str
    content_source_url: str = ""
    need_open_comment: int = 0
    only_fans_can_comment: int = 0
