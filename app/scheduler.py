import asyncio
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.pipeline import run_daily_publish


def start_scheduler() -> None:
    scheduler = BlockingScheduler(timezone=settings.tz)

    def job_wrapper() -> None:
        asyncio.run(run_daily_publish())

    scheduler.add_job(
        job_wrapper,
        CronTrigger.from_crontab(settings.publish_cron),
        id="daily_publish",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.start()
