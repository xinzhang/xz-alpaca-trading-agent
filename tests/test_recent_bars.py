"""get_recent_bars must return the *latest* bars — ending now during market hours, or at
the last close otherwise. Requesting `limit=N` without a start once returned the day's
first N bars, so every 15-minute cycle re-judged the same morning prices.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from alphadesk.clients.alpaca_client import AlpacaClient


class _FakeData:
    def __init__(self, bars: pd.DataFrame) -> None:
        self.bars = bars
        self.requests = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        return type("BarSet", (), {"df": self.bars})()


def _session(day: str, start: str, end: str) -> pd.DatetimeIndex:
    """Every minute in [start, end) ET on `day`, as UTC."""
    return pd.date_range(
        f"{day} {start}", f"{day} {end}", freq="1min", inclusive="left", tz="America/New_York"
    ).tz_convert("UTC")


def _client(bars: pd.DataFrame, extended_hours: bool = False) -> tuple[AlpacaClient, _FakeData]:
    client = AlpacaClient.__new__(AlpacaClient)
    client._data = _FakeData(bars)
    client._feed = None
    client._extended_hours = extended_hours
    return client, client._data


def _bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.DataFrame({"close": range(len(index))}, index=index)
    frame.index.name = "timestamp"
    return pd.concat({"IAU": frame}, names=["symbol"])  # alpaca-py's (symbol, ts) index


def test_returns_bars_ending_at_the_last_close_not_the_morning():
    # Thursday and Friday sessions with pre/post-market, as Alpaca returns them (ascending).
    index = _session("2026-10-29", "04:00", "20:00").append(
        _session("2026-10-30", "04:00", "20:00")
    )
    client, data = _client(_bars(index))

    bars = client.get_recent_bars("IAU", lookback_bars=100)

    eastern = bars.index.tz_convert("America/New_York")
    assert len(bars) == 100
    assert eastern[-1] == pd.Timestamp("2026-10-30 15:59", tz="America/New_York")
    assert eastern[0] == pd.Timestamp("2026-10-30 14:20", tz="America/New_York")
    request = data.requests[0]
    assert request.limit is None
    start = request.start.replace(tzinfo=request.start.tzinfo or UTC)  # alpaca-py: naive UTC
    assert datetime.now(UTC) - start >= timedelta(days=6)


def test_extended_hours_keeps_after_hours_bars():
    client, _ = _client(_bars(_session("2026-10-30", "04:00", "20:00")), extended_hours=True)
    bars = client.get_recent_bars("IAU", lookback_bars=100)
    assert bars.index.tz_convert("America/New_York")[-1] == pd.Timestamp(
        "2026-10-30 19:59", tz="America/New_York"
    )


def test_successive_cycles_see_newer_prices():
    morning = _session("2026-10-30", "09:30", "12:00")
    client, data = _client(_bars(morning))
    first = client.get_recent_bars("IAU")
    data.bars = _bars(morning.append(_session("2026-10-30", "12:00", "12:15")))
    second = client.get_recent_bars("IAU")
    assert second.index[-1] - first.index[-1] == pd.Timedelta(minutes=15)
