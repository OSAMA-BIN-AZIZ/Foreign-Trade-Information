from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from pathlib import Path

from app.config import settings
from app.exceptions import PublishPermissionError
from app.models import DailyDigest, DraftArticle
from app.notify.console import notify
from app.notify.webhook import notify_webhook
from app.render.article_builder import ArticleBuilder, write_output
from app.sources.calendar_info import format_gregorian, format_lunar
from app.sources.dedup import deduplicate_news, filter_trade_related, score_news
from app.sources.exchange_rate import CachedExchangeRateProvider, LiveExchangeRateProvider, MockExchangeRateProvider
from app.sources.news_http import HttpJsonNewsProvider
from app.sources.news_rss import RssNewsProvider
from app.storage.sqlite_store import SQLiteStateStore
from app.wechat.client import WeChatClient
from app.wechat.draft import create_draft
from app.wechat.media import upload_cover
from app.wechat.publish import poll_publish_status, submit_publish

logger = logging.getLogger(__name__)


_CJK_RE = re.compile(r"[一-鿿]")


def _is_chinese_text(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _infer_topic_cn(text: str) -> str:
    lower = (text or "").lower()
    mapping = {
        "tariff": "关税政策",
        "custom": "海关通关",
        "shipping": "国际航运",
        "logistics": "跨境物流",
        "fx": "汇率波动",
        "currency": "汇率波动",
        "export": "出口市场",
        "import": "进口市场",
        "trade": "国际贸易",
        "ecommerce": "跨境电商",
    }
    for key, value in mapping.items():
        if key in lower:
            return value
    return "国际贸易"


def _localize_news(item, idx: int):
    text = f"{item.title} {item.summary}"
    is_cn = _is_chinese_text(text)
    if is_cn:
        item.tags = ["国内"]
        return item

    topic = _infer_topic_cn(text)
    item.tags = ["国际"]
    item.title = f"国际外贸动态{idx}：{topic}"
    item.summary = f"该资讯来自国际公开新闻源，重点涉及{topic}，建议关注对出口订单、物流时效与收汇成本的影响。"
    return item


def _select_balanced_news(items, total: int, cn_min: int):
    cn = [i for i in items if _is_chinese_text(f"{i.title} {i.summary}")]
    global_items = [i for i in items if i not in cn]
    picked = cn[:cn_min] + global_items[: max(0, total - min(len(cn), cn_min))]
    if len(picked) < total:
        rest = [i for i in items if i not in picked]
        picked.extend(rest[: total - len(picked)])
    return picked[:total]



async def run_daily_publish(target_date: date | None = None, build_only: bool = False, mock_wechat: bool = True) -> dict:
    d = target_date or date.today()
    rate_inner = MockExchangeRateProvider()
    if settings.exchange_rate_provider in {"live", "auto"}:
        rate_inner = LiveExchangeRateProvider(timeout=settings.exchange_rate_timeout)
    rate_provider = CachedExchangeRateProvider(rate_inner, Path("data/cache/rates.json"))

    if settings.news_source_mode == "rss":
        legacy_urls = [u.strip() for u in settings.news_rss_urls.split(",") if u.strip()]
        cn_urls = [u.strip() for u in settings.news_cn_rss_urls.split(",") if u.strip()]
        global_urls = [u.strip() for u in settings.news_global_rss_urls.split(",") if u.strip()]
        rss_urls = legacy_urls or (cn_urls + global_urls)
        news_provider = RssNewsProvider(feed_urls=rss_urls, timeout=settings.news_fetch_timeout)
    else:
        news_provider = HttpJsonNewsProvider()
    state = SQLiteStateStore(settings.state_db)
    client = WeChatClient(settings.wechat_app_id, settings.wechat_app_secret, mock=mock_wechat)

    rate_fallback_used = False
    news_fallback_used = False

    try:
        rate = await rate_provider.fetch()
    except Exception:
        if settings.exchange_rate_provider == "auto":
            rate = await MockExchangeRateProvider().fetch()
            rate.stale = True
            rate_fallback_used = True
            logger.warning("汇率实时源不可用，已回退到降级数据", extra={"event": "fetch_rates_fallback_mock", "date": d.isoformat(), "status": "warn"})
        else:
            raise
    logger.info("汇率获取成功", extra={"event": "fetch_rates_ok", "date": d.isoformat(), "status": "ok"})

    fetched_items = await news_provider.fetch(settings.news_max_items * 4)
    items = filter_trade_related(fetched_items)
    news_fallback_used = bool(fetched_items) and all((it.source or "").startswith("Mock") for it in fetched_items)
    if news_fallback_used:
        logger.warning("新闻源不可用，已回退到降级数据", extra={"event": "fetch_news_fallback_mock", "date": d.isoformat(), "status": "warn"})
    if not items and fetched_items:
        items = fetched_items[: settings.news_min_items]

    items = score_news(deduplicate_news(items), {"MockRSS", "MockHTTP"})
    target_n = max(settings.news_min_items, min(len(items), settings.news_max_items))
    items = _select_balanced_news(items, total=target_n, cn_min=settings.news_cn_min_items)
    items = [_localize_news(i, idx=n) for n, i in enumerate(items, start=1)]
    logger.info("新闻获取成功", extra={"event": "fetch_news_ok", "date": d.isoformat(), "status": "ok"})

    notes: list[str] = []
    if rate_fallback_used:
        notes.append("汇率实时源不可用，当前为降级演示值（非最新）")
    elif rate.stale:
        notes.append("汇率为缓存数据，可能非最新")
    if news_fallback_used:
        notes.append("新闻源不可用或被限流，已降级为Mock示例")
    if fetched_items and not filter_trade_related(fetched_items):
        notes.append("未检索到足量高相关外贸资讯，已补充可能相关事件")

    digest = DailyDigest(
        title=f"{format_gregorian(d)}｜外贸与跨境资讯速览",
        date_text=format_gregorian(d),
        lunar_text=format_lunar(d),
        exchange_rate=rate,
        news_items=items,
        data_note="；".join(notes),
    )
    builder = ArticleBuilder(Path("app/render/templates"))
    digest = builder.build(digest)
    assert digest.markdown and digest.html

    content_hash = hashlib.sha256(digest.html.encode("utf-8")).hexdigest()
    if state.is_duplicate(d.isoformat(), content_hash):
        return {
            "status": "duplicate_skipped",
            "md": str(settings.output_dir / f"{d.isoformat()}.md"),
            "html": str(settings.output_dir / f"{d.isoformat()}.html"),
            "rate_fallback_used": rate_fallback_used,
            "news_fallback_used": news_fallback_used,
        }

    md_path, html_path = write_output(settings.output_dir, d, digest.markdown, digest.html)
    logger.info("内容渲染完成", extra={"event": "render_ok", "date": d.isoformat(), "status": "ok"})

    if build_only:
        return {
            "status": "built",
            "md": str(md_path),
            "html": str(html_path),
            "rate_fallback_used": rate_fallback_used,
            "news_fallback_used": news_fallback_used,
        }

    cover_path = settings.cover_image_path if settings.cover_image_path.exists() else Path("assets/cover-default.jpg")
    thumb_media_id = await upload_cover(client, str(cover_path))
    logger.info("封面上传成功", extra={"event": "upload_cover_ok", "date": d.isoformat(), "status": "ok"})

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
    logger.info("草稿创建成功", extra={"event": "draft_add_ok", "date": d.isoformat(), "status": "ok"})

    mode = "draft_only" if settings.wechat_use_draft_only else settings.publish_mode
    result = {
        "status": "draft_created",
        "draft_media_id": draft_media_id,
        "md": str(md_path),
        "html": str(html_path),
        "rate_fallback_used": rate_fallback_used,
        "news_fallback_used": news_fallback_used,
    }
    if mode == "draft_only":
        return result

    if state.has_submitted(draft_media_id):
        return {"status": "already_submitted", "draft_media_id": draft_media_id}

    try:
        publish_id = await submit_publish(client, draft_media_id)
        logger.info("发布任务提交成功", extra={"event": "freepublish_submit_ok", "date": d.isoformat(), "status": "ok"})
        status = await poll_publish_status(client, publish_id)
        state.mark_published(draft_media_id, publish_id, str(status.get("publish_status")))
        logger.info("发布状态获取成功", extra={"event": "publish_status_ok", "date": d.isoformat(), "status": "ok"})
        result.update({"status": "published", "publish_id": publish_id, "publish_status": status.get("publish_status")})
    except PublishPermissionError as exc:
        if mode == "safe_auto":
            logger.warning("自动发布权限不足，已降级为草稿", extra={"event": "fallback_to_draft_only", "date": d.isoformat(), "status": "warn"})
            notify(f"权限不足，已降级草稿模式: {exc.errcode}")
            await notify_webhook(settings.webhook_notify_url, f"权限不足，已降级草稿模式: {exc.errcode}")
            result.update({"status": "fallback_to_draft_only", "error": str(exc)})
        else:
            raise
    except Exception:
        logger.exception("任务执行失败", extra={"event": "job_failed", "date": d.isoformat(), "status": "error"})
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
