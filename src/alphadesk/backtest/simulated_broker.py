"""Implements the same `Broker` protocol as `AlpacaClient`, backed by preloaded
historical bars and an in-memory virtual portfolio — RiskAgent/SignalAgent/
ExecutionAgent run against this unmodified during a backtest.

Simplification, stated plainly rather than hidden: a cycle's Signal step sees that
day's own close (via `get_recent_bars`), and Execution fills at that same close price.
This is a close-to-close backtest, not an intraday-accurate one — it doesn't pretend to
know the day's price before the day's own bar closes, but it also doesn't model
next-day execution lag the way `btc-regime-bot`'s backtest does.
"""

from dataclasses import dataclass

import pandas as pd
from alpaca.trading.enums import OrderSide

from alphadesk.backtest.clock import SimulatedClock
from alphadesk.clients.alpaca_client import AccountSnapshot, PositionSnapshot


@dataclass(slots=True)
class SimOrder:
    id: str


@dataclass(slots=True)
class _SimPosition:
    qty: float
    avg_entry_price: float


class SimulatedBroker:
    def __init__(
        self,
        clock: SimulatedClock,
        historical_bars: dict[str, pd.DataFrame],
        initial_cash: float,
    ) -> None:
        self._clock = clock
        self._bars = historical_bars  # ticker -> full DataFrame, indexed by date, has 'close'
        self._cash = initial_cash
        self._positions: dict[str, _SimPosition] = {}
        self._order_seq = 0

    def _price_on(self, ticker: str) -> float:
        bars = self._bars[ticker]
        as_of = bars.loc[:self._clock.now]
        if as_of.empty:
            raise ValueError(f"no bars for {ticker} on or before {self._clock.now}")
        return float(as_of["close"].iloc[-1])

    def get_account(self) -> AccountSnapshot:
        positions_value = sum(
            pos.qty * self._price_on(ticker) for ticker, pos in self._positions.items()
        )
        equity = self._cash + positions_value
        return AccountSnapshot(
            equity=equity, cash=self._cash, buying_power=self._cash, portfolio_value=equity
        )

    def get_positions(self) -> dict[str, PositionSnapshot]:
        result = {}
        for ticker, pos in self._positions.items():
            price = self._price_on(ticker)
            market_value = pos.qty * price
            result[ticker] = PositionSnapshot(
                symbol=ticker,
                qty=pos.qty,
                market_value=market_value,
                avg_entry_price=pos.avg_entry_price,
                unrealized_pl=market_value - pos.qty * pos.avg_entry_price,
            )
        return result

    def get_recent_bars(self, symbol: str, lookback_bars: int = 100) -> pd.DataFrame:
        bars = self._bars[symbol]
        as_of = bars.loc[:self._clock.now]
        return as_of.tail(lookback_bars)

    def submit_market_order(
        self, symbol: str, side: OrderSide, qty: float | None = None, notional: float | None = None
    ) -> SimOrder:
        price = self._price_on(symbol)

        if side == OrderSide.BUY:
            if notional is None:
                raise ValueError("simulated BUY requires notional")
            bought_qty = notional / price
            existing = self._positions.get(symbol)
            if existing is None:
                self._positions[symbol] = _SimPosition(qty=bought_qty, avg_entry_price=price)
            else:
                total_qty = existing.qty + bought_qty
                blended_cost = existing.qty * existing.avg_entry_price + bought_qty * price
                self._positions[symbol] = _SimPosition(
                    qty=total_qty, avg_entry_price=blended_cost / total_qty
                )
            self._cash -= notional
        else:
            if qty is None:
                raise ValueError("simulated SELL requires qty")
            self._cash += qty * price
            del self._positions[symbol]

        self._order_seq += 1
        return SimOrder(id=f"SIM-{self._order_seq}")
