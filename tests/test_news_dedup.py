from app.models import NewsItem
from app.sources.dedup import deduplicate_news, score_news


def test_title_dedup() -> None:
    items = [
        NewsItem(source="a", title="关税新政 发布", summary="x", url="u1"),
        NewsItem(source="a", title="关税新政-发布", summary="y", url="u2"),
    ]
    out = deduplicate_news(items)
    assert len(out) == 1


def test_score_news() -> None:
    items = [
        NewsItem(source="white", title="跨境物流", summary="贸易海关", url="1"),
        NewsItem(source="other", title="普通新闻", summary="无", url="2"),
    ]
    ranked = score_news(items, {"white"})
    assert ranked[0].source == "white"
