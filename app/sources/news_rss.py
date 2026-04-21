from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

from app.models import NewsItem


class NewsProvider(Protocol):
    async def fetch(self, limit: int) -> list[NewsItem]: ...


class RssNewsProvider:
    def __init__(self, feed_urls: list[str] | None = None, timeout: float = 8.0) -> None:
        self.feed_urls = feed_urls or []
        self.timeout = timeout

    async def fetch(self, limit: int) -> list[NewsItem]:
        if not self.feed_urls:
            return self._mock_items(limit)

        items: list[NewsItem] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for feed_url in self.feed_urls:
                try:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    items.extend(self._parse_rss(resp.text, feed_url))
                except Exception:
                    continue

        if not items:
            return self._mock_items(limit)

        items.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return items[:limit]

    def _parse_rss(self, xml_text: str, feed_url: str) -> list[NewsItem]:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        source = urlparse(feed_url).netloc or "RSS"
        out: list[NewsItem] = []
        for node in channel.findall("item"):
            title = (node.findtext("title") or "").strip()
            if not title:
                continue
            summary = (node.findtext("description") or "").strip()
            link = (node.findtext("link") or "").strip() or None
            published_at = self._parse_pubdate(node.findtext("pubDate"))
            out.append(
                NewsItem(
                    source=source,
                    title=title,
                    summary=summary,
                    url=link,
                    published_at=published_at,
                )
            )
        return out

    @staticmethod
    def _parse_pubdate(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = parsedate_to_datetime(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _mock_items(limit: int) -> list[NewsItem]:
        now = datetime.now(timezone.utc)
        return [
            NewsItem(
                source="MockRSS",
                title=f"跨境电商物流动态 {i}",
                summary="多国口岸效率改善，跨境物流时效回升，平台卖家补货节奏前置。",
                url=f"https://example.com/rss/{i}",
                published_at=now - timedelta(hours=i),
            )
            for i in range(1, limit + 1)
        ]
