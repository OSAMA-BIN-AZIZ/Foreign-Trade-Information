from pathlib import Path

from app.models import ExchangeRate, NewsItem, DailyDigest
from app.render.article_builder import ArticleBuilder
from datetime import datetime, timezone
from decimal import Decimal


def test_markdown_render() -> None:
    digest = DailyDigest(
        title="测试标题",
        date_text="4月20日 星期一",
        lunar_text="农历三月初一",
        exchange_rate=ExchangeRate(base="CNY", usd_cny=Decimal("7.2"), eur_cny=Decimal("7.8"), as_of=datetime.now(timezone.utc)),
        news_items=[NewsItem(source="s", title="跨境电商", summary="摘要")],
    )
    built = ArticleBuilder(Path("app/render/templates")).build(digest)
    assert "测试标题" in (built.markdown or "")
    assert "<h1>" in (built.html or "")
