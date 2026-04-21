from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol
import json

import httpx

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


class LiveExchangeRateProvider:
    """Fetch live FX data from open.er-api.com and convert into CNY quotes."""

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    async def fetch(self) -> ExchangeRate:
        url = "https://open.er-api.com/v6/latest/USD"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

        rates = payload.get("rates") or {}
        try:
            usd_cny = Decimal(str(rates["CNY"]))
            usd_eur = Decimal(str(rates["EUR"]))
            eur_cny = usd_cny / usd_eur
        except (KeyError, InvalidOperation, ZeroDivisionError) as exc:
            raise ValueError("exchange rate payload missing required currencies") from exc

        as_of = datetime.fromtimestamp(int(payload.get("time_last_update_unix", 0)) or int(datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        return ExchangeRate(base="CNY", usd_cny=usd_cny, eur_cny=eur_cny.quantize(Decimal("0.0001")), as_of=as_of, stale=False)


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
