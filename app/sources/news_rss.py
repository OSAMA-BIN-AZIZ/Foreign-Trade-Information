from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.models import NewsItem


class NewsProvider(Protocol):
    async def fetch(self, limit: int) -> list[NewsItem]: ...


class RssNewsProvider:
    async def fetch(self, limit: int) -> list[NewsItem]:
        now = datetime.now(timezone.utc)
        items = [
            NewsItem(
                source="MockRSS",
                title=f"跨境电商物流动态 {i}",
                summary="多国口岸效率改善，跨境物流时效回升，平台卖家补货节奏前置。",
                url=f"https://example.com/rss/{i}",
                published_at=now - timedelta(hours=i),
            )
            for i in range(1, limit + 2)
        ]
        return items[:limit]
