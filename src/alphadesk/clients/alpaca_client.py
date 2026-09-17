"""Thin wrapper around alpaca-py: the only module that talks to Alpaca directly."""

from dataclasses import dataclass

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
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            limit=lookback_bars,
            feed=self._feed,
        )
        bars = self._data.get_stock_bars(request).df
        if bars.empty:
            return bars
        return bars.droplevel("symbol") if "symbol" in bars.index.names else bars

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
