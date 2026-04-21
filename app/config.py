from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    tz: str = "Asia/Shanghai"

    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_use_draft_only: bool = False
    wechat_author: str = "你的名字"
    wechat_need_open_comment: int = 0
    wechat_only_fans_can_comment: int = 0
    wechat_image_upload_mode: str = "auto"

    publish_cron: str = "0 8 * * *"
    output_dir: Path = Path("./data/output")
    state_db: Path = Path("./data/state.sqlite3")

    exchange_rate_provider: str = "auto"  # auto | live | mock
    exchange_rate_base: str = "CNY"
    exchange_rate_timeout: float = 8.0

    news_source_mode: str = "rss"
    news_rss_urls: str = "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best,https://www.cnbc.com/id/10001147/device/rss/rss.html"
    news_fetch_timeout: float = 8.0
    news_max_items: int = Field(default=12, ge=1)
    news_min_items: int = Field(default=8, ge=1)

    cover_image_path: Path = Path("./assets/cover-default.jpg")
    default_thumb_digest: str = "每日外贸与跨境资讯速览"

    webhook_notify_url: str = ""
    publish_mode: str = "safe_auto"  # draft_only | auto_publish | safe_auto


settings = Settings()
