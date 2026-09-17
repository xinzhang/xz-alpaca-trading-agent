"""Standard backtest performance stats, computed from the daily equity curve."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    start_equity: float
    end_equity: float
    total_return_pct: float
    annualized_sharpe: float
    max_drawdown_pct: float
    num_trades: int


def compute_metrics(equity_curve: pd.Series, num_trades: int) -> BacktestMetrics:
    daily_returns = equity_curve.pct_change().dropna()
    running_peak = equity_curve.cummax()
    drawdown = (equity_curve - running_peak) / running_peak

    sharpe = 0.0
    if daily_returns.std() > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252))

    return BacktestMetrics(
        start_equity=float(equity_curve.iloc[0]),
        end_equity=float(equity_curve.iloc[-1]),
        total_return_pct=float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1),
        annualized_sharpe=sharpe,
        max_drawdown_pct=float(drawdown.min()),
        num_trades=num_trades,
    )
