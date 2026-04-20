import pytest
from datetime import date

from app.pipeline import run_daily_publish
from app.config import settings


@pytest.mark.asyncio
async def test_pipeline_build_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    monkeypatch.setattr(settings, "state_db", tmp_path / "state.sqlite3")
    out = await run_daily_publish(target_date=date(2026,4,20), build_only=True)
    assert out["status"] == "built"


@pytest.mark.asyncio
async def test_safe_auto_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    monkeypatch.setattr(settings, "state_db", tmp_path / "state.sqlite3")
    monkeypatch.setattr(settings, "publish_mode", "safe_auto")
    out = await run_daily_publish(target_date=date(2026,4,21), build_only=False, mock_wechat=True)
    assert out["status"] in {"published", "draft_created", "fallback_to_draft_only"}
