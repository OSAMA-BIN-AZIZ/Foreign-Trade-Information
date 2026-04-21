from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from pathlib import Path

from app.config import settings
from app.exceptions import PublishPermissionError
from app.models import DailyDigest, DraftArticle
from app.notify.console import notify
from app.notify.webhook import notify_webhook
from app.render.article_builder import ArticleBuilder, write_output
from app.sources.calendar_info import format_gregorian, format_lunar
from app.sources.dedup import deduplicate_news, score_news
from app.sources.exchange_rate import CachedExchangeRateProvider, LiveExchangeRateProvider, MockExchangeRateProvider
from app.sources.news_http import HttpJsonNewsProvider
from app.sources.news_rss import RssNewsProvider
from app.storage.sqlite_store import SQLiteStateStore
from app.wechat.client import WeChatClient
from app.wechat.draft import create_draft
from app.wechat.media import upload_cover
from app.wechat.publish import poll_publish_status, submit_publish

logger = logging.getLogger(__name__)


async def run_daily_publish(target_date: date | None = None, build_only: bool = False, mock_wechat: bool = True) -> dict:
    d = target_date or date.today()
    rate_inner = MockExchangeRateProvider()
    if settings.exchange_rate_provider in {"live", "auto"}:
        rate_inner = LiveExchangeRateProvider(timeout=settings.exchange_rate_timeout)
    rate_provider = CachedExchangeRateProvider(rate_inner, Path("data/cache/rates.json"))

    if settings.news_source_mode == "rss":
        rss_urls = [u.strip() for u in settings.news_rss_urls.split(",") if u.strip()]
        news_provider = RssNewsProvider(feed_urls=rss_urls, timeout=settings.news_fetch_timeout)
    else:
        news_provider = HttpJsonNewsProvider()
    state = SQLiteStateStore(settings.state_db)
    client = WeChatClient(settings.wechat_app_id, settings.wechat_app_secret, mock=mock_wechat)

    try:
        rate = await rate_provider.fetch()
    except Exception:
        if settings.exchange_rate_provider == "auto":
            rate = await MockExchangeRateProvider().fetch()
            logger.warning("fetch_rates_fallback_mock", extra={"event": "fetch_rates_fallback_mock", "date": d.isoformat(), "status": "warn"})
        else:
            raise
    logger.info("fetch_rates_ok", extra={"event": "fetch_rates_ok", "date": d.isoformat(), "status": "ok"})

    items = await news_provider.fetch(settings.news_max_items)
    items = score_news(deduplicate_news(items), {"MockRSS", "MockHTTP"})[: settings.news_max_items]
    items = items[: max(settings.news_min_items, min(len(items), settings.news_max_items))]
    logger.info("fetch_news_ok", extra={"event": "fetch_news_ok", "date": d.isoformat(), "status": "ok"})

    digest = DailyDigest(
        title=f"{format_gregorian(d)}｜外贸与跨境资讯速览",
        date_text=format_gregorian(d),
        lunar_text=format_lunar(d),
        exchange_rate=rate,
        news_items=items,
    )
    builder = ArticleBuilder(Path("app/render/templates"))
    digest = builder.build(digest)
    assert digest.markdown and digest.html

    content_hash = hashlib.sha256(digest.html.encode("utf-8")).hexdigest()
    if state.is_duplicate(d.isoformat(), content_hash):
        return {"status": "duplicate_skipped"}

    md_path, html_path = write_output(settings.output_dir, d, digest.markdown, digest.html)
    logger.info("render_ok", extra={"event": "render_ok", "date": d.isoformat(), "status": "ok"})

    if build_only:
        return {"status": "built", "md": str(md_path), "html": str(html_path)}

    cover_path = settings.cover_image_path if settings.cover_image_path.exists() else Path("assets/cover-default.jpg")
    thumb_media_id = await upload_cover(client, str(cover_path))
    logger.info("upload_cover_ok", extra={"event": "upload_cover_ok", "date": d.isoformat(), "status": "ok"})

    article = DraftArticle(
        title=digest.title,
        author=settings.wechat_author,
        digest=settings.default_thumb_digest,
        content=digest.html,
        thumb_media_id=thumb_media_id,
        need_open_comment=settings.wechat_need_open_comment,
        only_fans_can_comment=settings.wechat_only_fans_can_comment,
    )
    draft_media_id = await create_draft(client, article)
    state.save_draft(d.isoformat(), content_hash, draft_media_id)
    logger.info("draft_add_ok", extra={"event": "draft_add_ok", "date": d.isoformat(), "status": "ok"})

    mode = "draft_only" if settings.wechat_use_draft_only else settings.publish_mode
    result = {"status": "draft_created", "draft_media_id": draft_media_id}
    if mode == "draft_only":
        return result

    if state.has_submitted(draft_media_id):
        return {"status": "already_submitted", "draft_media_id": draft_media_id}

    try:
        publish_id = await submit_publish(client, draft_media_id)
        logger.info("freepublish_submit_ok", extra={"event": "freepublish_submit_ok", "date": d.isoformat(), "status": "ok"})
        status = await poll_publish_status(client, publish_id)
        state.mark_published(draft_media_id, publish_id, str(status.get("publish_status")))
        logger.info("publish_status_ok", extra={"event": "publish_status_ok", "date": d.isoformat(), "status": "ok"})
        result.update({"status": "published", "publish_id": publish_id, "publish_status": status.get("publish_status")})
    except PublishPermissionError as exc:
        if mode == "safe_auto":
            logger.warning("fallback_to_draft_only", extra={"event": "fallback_to_draft_only", "date": d.isoformat(), "status": "warn"})
            notify(f"权限不足，已降级草稿模式: {exc.errcode}")
            await notify_webhook(settings.webhook_notify_url, f"权限不足，已降级草稿模式: {exc.errcode}")
            result.update({"status": "fallback_to_draft_only", "error": str(exc)})
        else:
            raise
    except Exception:
        logger.exception("job_failed", extra={"event": "job_failed", "date": d.isoformat(), "status": "error"})
        raise

    return result


async def publish_existing_draft(digest_date: str, mock_wechat: bool = True) -> dict:
    state = SQLiteStateStore(settings.state_db)
    client = WeChatClient(settings.wechat_app_id, settings.wechat_app_secret, mock=mock_wechat)
    import sqlite3

    with sqlite3.connect(settings.state_db) as con:
        row = con.execute("SELECT draft_media_id FROM publish_state WHERE digest_date=? ORDER BY created_at DESC LIMIT 1", (digest_date,)).fetchone()
    if not row:
        return {"status": "not_found"}
    draft_media_id = row[0]
    if state.has_submitted(draft_media_id):
        return {"status": "already_submitted", "draft_media_id": draft_media_id}
    publish_id = await submit_publish(client, draft_media_id)
    status = await poll_publish_status(client, publish_id)
    state.mark_published(draft_media_id, publish_id, str(status.get("publish_status")))
    return {"status": "published", "publish_id": publish_id}
