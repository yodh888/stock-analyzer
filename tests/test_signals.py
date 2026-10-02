import pandas as pd
import pytest

from signals import generate_comprehensive_signal


def make_kline(bars: int) -> pd.DataFrame:
    close = [10 + index * 0.02 for index in range(bars)]
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=bars),
        "open": [value - 0.03 for value in close],
        "high": [value + 0.10 for value in close],
        "low": [value - 0.10 for value in close],
        "close": close,
        "volume": [1000 + index * 10 for index in range(bars)],
        "amount": [1_000_000 + index * 1000 for index in range(bars)],
        "pct_change": [0.0] + [0.2] * (bars - 1),
        "change": [0.0] + [0.02] * (bars - 1),
        "turnover": [1.0] * bars,
    })


@pytest.mark.parametrize("bars", [1, 20, 59])
def test_short_data_returns_error_instead_of_raising(bars):
    result = generate_comprehensive_signal(make_kline(bars))
    assert "error" in result
    assert result["data_bars"] == bars


def test_empty_data_returns_error():
    result = generate_comprehensive_signal(pd.DataFrame())
    assert result["error"] == "数据为空"


def test_sixty_bars_generates_complete_signal():
    result = generate_comprehensive_signal(make_kline(60))
    assert "error" not in result
    assert result["data_bars"] == 60
    assert {"suggestion", "action", "total_score", "details"} <= result.keys()
