from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Protocol
import json

from app.models import ExchangeRate


class ExchangeRateProvider(Protocol):
    async def fetch(self) -> ExchangeRate: ...


class MockExchangeRateProvider:
    async def fetch(self) -> ExchangeRate:
        return ExchangeRate(
            base="CNY",
            usd_cny=Decimal("7.2100"),
            eur_cny=Decimal("7.8900"),
            as_of=datetime.now(timezone.utc),
            stale=False,
        )


class CachedExchangeRateProvider:
    def __init__(self, inner: ExchangeRateProvider, cache_file: Path) -> None:
        self.inner = inner
        self.cache_file = cache_file

    async def fetch(self) -> ExchangeRate:
        try:
            rate = await self.inner.fetch()
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(rate.model_dump_json(), encoding="utf-8")
            return rate
        except Exception:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                return ExchangeRate(**data, stale=True)
            raise
