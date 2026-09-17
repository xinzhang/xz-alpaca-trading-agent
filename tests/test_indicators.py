import pandas as pd

from alphadesk.indicators import compute_snapshot, rsi, sma


def _bars(prices: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": prices})


def test_sma_matches_manual_average():
    bars = _bars([10, 20, 30, 40, 50])
    result = sma(bars["close"], period=5)
    assert result.iloc[-1] == 30


def test_rsi_is_100_when_price_only_rises():
    prices = list(range(1, 30))  # strictly increasing -> no losses -> RSI -> 100
    result = rsi(pd.Series(prices, dtype=float), period=14)
    assert result.iloc[-1] > 99


def test_rsi_is_0_when_price_only_falls():
    prices = list(range(30, 1, -1))  # strictly decreasing -> no gains -> RSI -> 0
    result = rsi(pd.Series(prices, dtype=float), period=14)
    assert result.iloc[-1] < 1


def test_compute_snapshot_returns_none_before_period_warms_up():
    bars = _bars([100.0, 101.0, 99.5])  # far fewer than the 20-period window
    snapshot = compute_snapshot(bars)
    assert snapshot.last_price == 99.5
    assert snapshot.sma_20 is None
    assert snapshot.bollinger_upper is None


def test_compute_snapshot_populates_all_fields_once_warmed_up():
    prices = [100.0 + (i % 5) for i in range(40)]
    snapshot = compute_snapshot(_bars(prices))
    assert snapshot.sma_20 is not None
    assert snapshot.ema_20 is not None
    assert snapshot.bollinger_upper is not None
    assert snapshot.bollinger_upper >= snapshot.bollinger_lower
