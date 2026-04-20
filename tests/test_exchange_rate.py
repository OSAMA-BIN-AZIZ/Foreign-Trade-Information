import pytest
from app.sources.exchange_rate import MockExchangeRateProvider


@pytest.mark.asyncio
async def test_mock_exchange_rate() -> None:
    rate = await MockExchangeRateProvider().fetch()
    assert rate.usd_cny > 0
    assert rate.eur_cny > 0
