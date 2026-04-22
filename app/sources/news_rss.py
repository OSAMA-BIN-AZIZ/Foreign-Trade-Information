from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import logging

import httpx

from app.models import NewsItem


class NewsProvider(Protocol):
    async def fetch(self, limit: int) -> list[NewsItem]: ...


class RssNewsProvider:
    @staticmethod
    def _format_fetch_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTP {exc.response.status_code}"
        if isinstance(exc, httpx.RequestError):
            return f"网络错误: {exc.__class__.__name__}"
        return str(exc) or exc.__class__.__name__

    def __init__(self, feed_urls: list[str] | None = None, timeout: float = 8.0, proxy: str = "", proxy_mode: str = "auto", retry_count: int = 2, retry_backoff_sec: float = 0.6) -> None:
        self.feed_urls = feed_urls or []
        self.timeout = timeout
        self.proxy = proxy or None
        self.proxy_mode = proxy_mode
        self.retry_count = max(1, retry_count)
        self.retry_backoff_sec = retry_backoff_sec
        self.logger = logging.getLogger(__name__)

    def _proxy_attempts(self) -> list[bool]:
        if self.proxy_mode == "on":
            return [True]
        if self.proxy_mode == "off":
            return [False]
        return [False, True] if self.proxy else [False]

    async def _fetch_feed_text(self, feed_url: str, headers: dict[str, str]) -> str:
        last_error: Exception | None = None
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
        ]
        for use_proxy in self._proxy_attempts():
            for attempt in range(1, self.retry_count + 1):
                try:
                    req_headers = {**headers, "User-Agent": user_agents[(attempt - 1) % len(user_agents)]}
                    async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=req_headers, proxy=(self.proxy if use_proxy else None), trust_env=True) as client:
                        resp = await client.get(feed_url)
                        resp.raise_for_status()
                        return resp.text
                except Exception as exc:
                    last_error = exc
                    if attempt < self.retry_count:
                        await asyncio.sleep(self.retry_backoff_sec * attempt)
                    continue
        detail = self._format_fetch_error(last_error) if last_error else "unknown"
        raise RuntimeError(f"feed request failed: {feed_url} ({detail})") from last_error

    async def fetch(self, limit: int) -> list[NewsItem]:
        if not self.feed_urls:
            return self._mock_items(limit)

        items: list[NewsItem] = []
        headers = {
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        }
        for feed_url in self.feed_urls:
            try:
                text = await self._fetch_feed_text(feed_url, headers)
                parsed = self._parse_rss(text, feed_url)
                items.extend(parsed)
                self.logger.info("RSS源抓取成功", extra={"event": "rss_feed_ok", "status": "ok", "feed_url": feed_url, "fetched": len(parsed)})
            except Exception as exc:
                self.logger.warning("RSS源抓取失败", extra={"event": "rss_feed_fail", "status": "warn", "feed_url": feed_url, "error": self._format_fetch_error(exc)})
                continue

        if not items:
            self.logger.warning("全部RSS源失败，使用Mock新闻", extra={"event": "rss_all_failed", "status": "warn"})
            return self._mock_items(limit)

        items.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return items[:limit]

    def _parse_rss(self, xml_text: str, feed_url: str) -> list[NewsItem]:
        root = ET.fromstring(xml_text)
        source = urlparse(feed_url).netloc or "RSS"

        # RSS 2.0
        channel = root.find("channel")
        if channel is not None:
            return self._parse_rss_channel(channel, source)

        # Atom
        if root.tag.endswith("feed"):
            return self._parse_atom_feed(root, source)

        return []

    def _parse_rss_channel(self, channel: ET.Element, source: str) -> list[NewsItem]:
        out: list[NewsItem] = []
        for node in channel.findall("item"):
            title = (node.findtext("title") or "").strip()
            if not title:
                continue
            summary = (node.findtext("description") or "").strip()
            link = (node.findtext("link") or "").strip() or None
            published_at = self._parse_pubdate(node.findtext("pubDate"))
            out.append(NewsItem(source=source, title=title, summary=summary, url=link, published_at=published_at))
        return out

    def _parse_atom_feed(self, root: ET.Element, source: str) -> list[NewsItem]:
        out: list[NewsItem] = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns) or root.findall("entry")
        for node in entries:
            title = (node.findtext("atom:title", default="", namespaces=ns) or node.findtext("title") or "").strip()
            if not title:
                continue
            summary = (
                (node.findtext("atom:summary", default="", namespaces=ns) or node.findtext("summary") or "")
                or (node.findtext("atom:content", default="", namespaces=ns) or node.findtext("content") or "")
            ).strip()
            link_node = node.find("atom:link", ns) or node.find("link")
            link = None
            if link_node is not None:
                link = (link_node.get("href") or "").strip() or (link_node.text or "").strip() or None
            published_at = self._parse_pubdate(
                node.findtext("atom:updated", default=None, namespaces=ns)
                or node.findtext("updated")
                or node.findtext("atom:published", default=None, namespaces=ns)
                or node.findtext("published")
            )
            out.append(NewsItem(source=source, title=title, summary=summary, url=link, published_at=published_at))
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
