from __future__ import annotations

import asyncio
from datetime import date, timedelta

import typer

from app.config import settings
from app.logging_setup import setup_logging
from app.models import DraftArticle
from app.pipeline import publish_existing_draft, run_daily_publish
from app.scheduler import start_scheduler
from app.wechat.auth import get_token
from app.wechat.client import WeChatClient
from app.wechat.draft import create_draft
from app.wechat.media import upload_cover

app = typer.Typer()


@app.command("run-once")
def run_once() -> None:
    setup_logging()
    result = asyncio.run(run_daily_publish())
    typer.echo(result)


@app.command("build-only")
def build_only() -> None:
    setup_logging()
    result = asyncio.run(run_daily_publish(build_only=True))
    typer.echo(result)


@app.command("publish-draft")
def publish_draft(date_str: str = typer.Option(..., "--date")) -> None:
    setup_logging()
    result = asyncio.run(publish_existing_draft(date_str))
    typer.echo(result)


@app.command("check-wechat")
def check_wechat(mock: bool = typer.Option(True, help="是否使用 mock 模式")) -> None:
    """检查 token、封面上传、草稿创建链路。"""
    setup_logging()
    client = WeChatClient(app_id=settings.wechat_app_id, app_secret=settings.wechat_app_secret, mock=mock)
    token = asyncio.run(get_token(client))

    if mock:
        typer.echo({"ok": True, "mode": "mock", "token_prefix": token[:4] + "***"})
        return

    cover_path = settings.cover_image_path if settings.cover_image_path.exists() else settings.cover_image_path
    thumb_media_id = asyncio.run(upload_cover(client, str(cover_path)))
    article = DraftArticle(
        title="连通性检查草稿",
        author=settings.wechat_author,
        digest="check-wechat",
        content="<p>check-wechat draft</p>",
        thumb_media_id=thumb_media_id,
        need_open_comment=settings.wechat_need_open_comment,
        only_fans_can_comment=settings.wechat_only_fans_can_comment,
    )
    draft_media_id = asyncio.run(create_draft(client, article))
    typer.echo({
        "ok": True,
        "mode": "real",
        "token_prefix": token[:4] + "***",
        "thumb_media_id": thumb_media_id,
        "draft_media_id": draft_media_id,
    })


@app.command("backfill")
def backfill(start: date = typer.Option(...), end: date = typer.Option(...)) -> None:
    setup_logging()
    current = start
    while current <= end:
        result = asyncio.run(run_daily_publish(target_date=current))
        typer.echo({"date": current.isoformat(), "result": result})
        current += timedelta(days=1)


@app.command("scheduler")
def scheduler_cmd() -> None:
    setup_logging()
    start_scheduler()


if __name__ == "__main__":
    app()
