from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol
import json
import logging

import httpx

from app.models import ExchangeRate

logger = logging.getLogger(__name__)


class ExchangeRateProvider(Protocol):
    async def fetch(self) -> ExchangeRate: ...


class MockExchangeRateProvider:
    def _proxy_attempts(self) -> list[bool]:
        if self.proxy_mode == "on":
            return [True]
        if self.proxy_mode == "off":
            return [False]
        # auto: 先直连，失败再走代理
        return [False, True] if self.proxy else [False]

    async def _request_json(self, url: str) -> dict:
        last_error: Exception | None = None
        for use_proxy in self._proxy_attempts():
            try:
                async with httpx.AsyncClient(timeout=self.timeout, proxy=(self.proxy if use_proxy else None), trust_env=True) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"request failed: {url}") from last_error

    async def fetch(self) -> ExchangeRate:
        return ExchangeRate(
            base="CNY",
            usd_cny=Decimal("6.9000"),
            eur_cny=Decimal("7.5000"),
            as_of=datetime.now(timezone.utc),
            stale=True,
        )


class LiveExchangeRateProvider:
    """Fetch live FX data with multi-source fallback."""

    def __init__(self, timeout: float = 8.0, proxy: str = "", proxy_mode: str = "auto") -> None:
        self.timeout = timeout
        self.proxy = proxy or None
        self.proxy_mode = proxy_mode

    def _proxy_attempts(self) -> list[bool]:
        if self.proxy_mode == "on":
            return [True]
        if self.proxy_mode == "off":
            return [False]
        # auto: 先直连，失败再走代理
        return [False, True] if self.proxy else [False]

    async def _request_json(self, url: str) -> dict:
        last_error: Exception | None = None
        for use_proxy in self._proxy_attempts():
            try:
                async with httpx.AsyncClient(timeout=self.timeout, proxy=(self.proxy if use_proxy else None), trust_env=True) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"request failed: {url}") from last_error

    async def fetch(self) -> ExchangeRate:
        last_error: Exception | None = None
        for loader in (self._fetch_from_open_er_api, self._fetch_from_frankfurter, self._fetch_from_exchange_rate_api):
            try:
                rate = await loader()
                logger.info("汇率源拉取成功", extra={"event": "fx_source_ok", "status": "ok", "provider": loader.__name__})
                return rate
            except Exception as exc:
                last_error = exc
                logger.warning("汇率源拉取失败", extra={"event": "fx_source_fail", "status": "warn", "provider": loader.__name__, "error": str(exc)})
                continue
        raise RuntimeError("all live exchange-rate sources failed") from last_error

    async def _fetch_from_open_er_api(self) -> ExchangeRate:
        url = "https://open.er-api.com/v6/latest/USD"
        payload = await self._request_json(url)

        rates = payload.get("rates") or {}
        usd_cny, eur_cny = self._extract_usd_eur_cny(rates)
        as_of = datetime.fromtimestamp(
            int(payload.get("time_last_update_unix", 0)) or int(datetime.now(timezone.utc).timestamp()),
            tz=timezone.utc,
        )
        return ExchangeRate(base="CNY", usd_cny=usd_cny, eur_cny=eur_cny, as_of=as_of, stale=False)

    async def _fetch_from_frankfurter(self) -> ExchangeRate:
        # 使用 EUR 为基准，直接拿到 EUR/CNY，减少交叉换算误差
        url = "https://api.frankfurter.app/latest?from=EUR&to=CNY,USD"
        payload = await self._request_json(url)

        rates = payload.get("rates") or {}
        try:
            eur_cny = Decimal(str(rates["CNY"]))
            eur_usd = Decimal(str(rates["USD"]))
            usd_cny = (eur_cny / eur_usd).quantize(Decimal("0.0001"))
        except (KeyError, InvalidOperation, ZeroDivisionError) as exc:
            raise ValueError("frankfurter payload missing required currencies") from exc

        date_str = payload.get("date")
        as_of = datetime.fromisoformat(f"{date_str}T00:00:00+00:00") if date_str else datetime.now(timezone.utc)
        return ExchangeRate(base="CNY", usd_cny=usd_cny, eur_cny=eur_cny.quantize(Decimal("0.0001")), as_of=as_of, stale=False)


    async def _fetch_from_exchange_rate_api(self) -> ExchangeRate:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        payload = await self._request_json(url)

        rates = payload.get("rates") or {}
        usd_cny, eur_cny = self._extract_usd_eur_cny(rates)
        time_str = payload.get("time_last_updated") or payload.get("date")
        if isinstance(time_str, str) and len(time_str) >= 10:
            as_of = datetime.fromisoformat(f"{time_str[:10]}T00:00:00+00:00")
        else:
            as_of = datetime.now(timezone.utc)
        return ExchangeRate(base="CNY", usd_cny=usd_cny, eur_cny=eur_cny, as_of=as_of, stale=False)
    @staticmethod
    def _extract_usd_eur_cny(rates: dict) -> tuple[Decimal, Decimal]:
        try:
            usd_cny = Decimal(str(rates["CNY"]))
            usd_eur = Decimal(str(rates["EUR"]))
            eur_cny = (usd_cny / usd_eur).quantize(Decimal("0.0001"))
        except (KeyError, InvalidOperation, ZeroDivisionError) as exc:
            raise ValueError("exchange rate payload missing required currencies") from exc
        return usd_cny, eur_cny


class CachedExchangeRateProvider:
    def __init__(self, inner: ExchangeRateProvider, cache_file: Path) -> None:
        self.inner = inner
        self.cache_file = cache_file

    def _proxy_attempts(self) -> list[bool]:
        if self.proxy_mode == "on":
            return [True]
        if self.proxy_mode == "off":
            return [False]
        # auto: 先直连，失败再走代理
        return [False, True] if self.proxy else [False]

    async def _request_json(self, url: str) -> dict:
        last_error: Exception | None = None
        for use_proxy in self._proxy_attempts():
            try:
                async with httpx.AsyncClient(timeout=self.timeout, proxy=(self.proxy if use_proxy else None), trust_env=True) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"request failed: {url}") from last_error

    async def fetch(self) -> ExchangeRate:
        try:
            rate = await self.inner.fetch()
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(rate.model_dump_json(), encoding="utf-8")
            return rate
        except Exception as exc:
            if self.cache_file.exists():
                logger.warning("实时汇率失败，使用本地缓存", extra={"event": "fx_use_cache", "status": "warn", "error": str(exc)})
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                return ExchangeRate(**data, stale=True)
            raise
