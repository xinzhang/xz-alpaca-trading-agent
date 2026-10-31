"""Thin wrapper around alpaca-py: the only module that talks to Alpaca directly."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from alphadesk.config import Settings


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    symbol: str
    qty: float
    market_value: float
    avg_entry_price: float
    unrealized_pl: float


class AlpacaClient:
    """Wraps the Alpaca trading + market-data clients for the paper account."""

    def __init__(self, settings: Settings) -> None:
        self._trading = TradingClient(
            settings.alpaca_api_key, settings.alpaca_secret_key, paper=settings.alpaca_paper
        )
        self._data = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
        self._feed = DataFeed.SIP if settings.alpaca_data_feed.upper() == "SIP" else DataFeed.IEX
        self._extended_hours = settings.include_extended_hours

    def is_market_open(self) -> bool:
        return bool(self._trading.get_clock().is_open)

    def get_account(self) -> AccountSnapshot:
        account = self._trading.get_account()
        return AccountSnapshot(
            equity=float(account.equity),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            portfolio_value=float(account.portfolio_value),
        )

    def get_positions(self) -> dict[str, PositionSnapshot]:
        positions = self._trading.get_all_positions()
        return {
            p.symbol: PositionSnapshot(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
                avg_entry_price=float(p.avg_entry_price),
                unrealized_pl=float(p.unrealized_pl),
            )
            for p in positions
        }

    def get_recent_bars(self, symbol: str, lookback_bars: int = 100) -> pd.DataFrame:
        """The most recent `lookback_bars` 1-minute bars, oldest first. Outside market
        hours that ends at the last close (or the last after-hours trade when extended
        hours are included). A bare `limit` without `start` would instead return the
        *first* bars of the current day, freezing indicators on the morning session."""
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            # A week spans any weekend plus a holiday; at most ~5 sessions of bars.
            start=datetime.now(UTC) - timedelta(days=7),
            feed=self._feed,
        )
        bars = self._data.get_stock_bars(request).df
        if bars.empty:
            return bars
        if "symbol" in bars.index.names:
            bars = bars.droplevel("symbol")
        if not self._extended_hours:
            bars = regular_session(bars)
        return bars.tail(lookback_bars)


def regular_session(bars: pd.DataFrame) -> pd.DataFrame:
    """Keeps 9:30-16:00 ET bars; pre/post-market prints on IEX are thin and noisy."""
    eastern = bars.index.tz_convert("America/New_York")
    minutes = eastern.hour * 60 + eastern.minute
    return bars[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)]

    def submit_market_order(
        self, symbol: str, side: OrderSide, qty: float | None = None, notional: float | None = None
    ):
        request = MarketOrderRequest(
            symbol=symbol,
            side=side,
            time_in_force=TimeInForce.DAY,
            qty=qty,
            notional=notional,
        )
        return self._trading.submit_order(request)
