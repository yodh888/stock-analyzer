from datetime import date

import pandas as pd

import data_fetcher
from data_fetcher import _normalize_kline, _to_float


def test_to_float_handles_percent_and_missing_values():
    assert _to_float("12.34%") == 12.34
    assert _to_float("1,234.5") == 1234.5
    assert _to_float("--") is None
    assert _to_float(float("nan")) is None


def test_normalize_kline_drops_duplicates_and_sorts():
    raw = pd.DataFrame({
        "date": ["2026-01-03", "2026-01-01", "2026-01-03"],
        "open": [11, 10, 11.5],
        "high": [12, 11, 12.5],
        "low": [10, 9, 10.5],
        "close": [11.5, 10.5, 12],
        "volume": [100, 200, 300],
    })
    normalized = _normalize_kline(raw, "test")
    assert len(normalized) == 2
    assert normalized["date"].is_monotonic_increasing
    assert normalized.iloc[-1]["close"] == 12
    assert normalized.attrs["source"] == "test"


def test_is_trade_day_uses_calendar(monkeypatch):
    monkeypatch.setattr(data_fetcher, "_get_trade_dates", lambda: {date(2026, 10, 2)})
    assert data_fetcher.is_trade_day(date(2026, 10, 2)) is True
    assert data_fetcher.is_trade_day(date(2026, 10, 3)) is False


def test_is_trade_day_fails_open(monkeypatch):
    def fail():
        raise RuntimeError("network down")

    monkeypatch.setattr(data_fetcher, "_get_trade_dates", fail)
    assert data_fetcher.is_trade_day(date(2026, 10, 2)) is True
