from datetime import datetime, timedelta, timezone

from app.models import NewsItem


class HttpJsonNewsProvider:
    async def fetch(self, limit: int) -> list[NewsItem]:
        now = datetime.now(timezone.utc)
        return [
            NewsItem(
                source="MockHTTP",
                title=f"关税与汇率观察 {i}",
                summary="美元指数震荡叠加海运价格波动，出口企业加快锁汇与多港口分流。",
                url=f"https://example.com/http/{i}",
                published_at=now - timedelta(minutes=i * 30),
            )
            for i in range(1, limit + 1)
        ]
