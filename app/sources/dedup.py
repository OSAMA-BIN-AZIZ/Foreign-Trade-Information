import re
from difflib import SequenceMatcher

from app.models import NewsItem

KEYWORDS = ["贸易", "跨境", "物流", "关税", "汇率", "海关"]


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", "", title).lower().strip()


def deduplicate_news(items: list[NewsItem]) -> list[NewsItem]:
    by_url: dict[str, NewsItem] = {}
    for item in items:
        if item.url and item.url not in by_url:
            by_url[item.url] = item
    if not by_url:
        by_url = {str(i): item for i, item in enumerate(items)}

    unique: list[NewsItem] = []
    seen: list[str] = []
    for item in by_url.values():
        norm = normalize_title(item.title)
        if norm in seen:
            continue
        if any(SequenceMatcher(None, norm, t).ratio() > 0.9 for t in seen):
            continue
        seen.append(norm)
        unique.append(item)
    return unique


def score_news(items: list[NewsItem], source_whitelist: set[str] | None = None) -> list[NewsItem]:
    source_whitelist = source_whitelist or set()
    for item in items:
        score = 0.0
        if item.source in source_whitelist:
            score += 2
        if item.published_at:
            score += 1
        if any(k in item.title + item.summary for k in KEYWORDS):
            score += 2
        title_len = len(item.title)
        if 8 <= title_len <= 30:
            score += 1
        item.score = score
    return sorted(items, key=lambda x: x.score, reverse=True)
