import pytest

from app.cli import parse_iso_date


def test_parse_iso_date_ok() -> None:
    d = parse_iso_date("2026-04-20", "start")
    assert d.year == 2026 and d.month == 4 and d.day == 20


def test_parse_iso_date_invalid() -> None:
    with pytest.raises(Exception):
        parse_iso_date("2026/04/20", "start")
