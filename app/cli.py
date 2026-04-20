from __future__ import annotations

import asyncio
from datetime import date, timedelta

import typer

from app.logging_setup import setup_logging
from app.pipeline import publish_existing_draft, run_daily_publish
from app.wechat.auth import get_token
from app.wechat.client import WeChatClient
from app.scheduler import start_scheduler

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
def check_wechat() -> None:
    setup_logging()
    client = WeChatClient(app_id="", app_secret="", mock=True)
    token = asyncio.run(get_token(client))
    typer.echo({"ok": True, "token_prefix": token[:4] + "***"})


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
