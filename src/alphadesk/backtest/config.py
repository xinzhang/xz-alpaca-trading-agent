"""Parameters for one backtest run — distinct from the live app's `Settings`, since
things like `initial_cash` and a date range only make sense for a historical replay."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    tickers: list[str]
    start: date
    end: date
    initial_cash: float = 50_000.0
    lookback_buffer_days: int = 90  # extra history fetched before `start` to warm up indicators
