"""The interface SignalAgent/RiskAgent/ExecutionAgent actually depend on.

`AlpacaClient` (live) and `backtest.simulated_broker.SimulatedBroker` (historical replay)
both satisfy this structurally — agents are written against this Protocol, not against
`AlpacaClient` directly, so a backtest can run the exact same agent code unmodified.
"""

from typing import Protocol

import pandas as pd
from alpaca.trading.enums import OrderSide

from alphadesk.clients.alpaca_client import AccountSnapshot, PositionSnapshot


class Broker(Protocol):
    def get_account(self) -> AccountSnapshot: ...

    def get_positions(self) -> dict[str, PositionSnapshot]: ...

    def get_recent_bars(self, symbol: str, lookback_bars: int = 100) -> pd.DataFrame: ...

    def submit_market_order(
        self, symbol: str, side: OrderSide, qty: float | None = None, notional: float | None = None
    ): ...
