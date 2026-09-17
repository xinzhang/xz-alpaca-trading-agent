"""Walks the pipeline forward, one simulated trading day at a time, over the
configured date range, recording the equity curve and every decision made.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

from alphadesk.backtest.config import BacktestConfig
from alphadesk.backtest.data_loader import trading_days
from alphadesk.backtest.wiring import BacktestContainer, build_backtest_container
from alphadesk.config import Settings
from alphadesk.pipeline import decision_summary

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BacktestResult:
    equity_curve: pd.Series
    decisions_log: list[dict] = field(default_factory=list)
    num_trades: int = 0


async def run_backtest(settings: Settings, config: BacktestConfig) -> BacktestResult:
    container: BacktestContainer = await build_backtest_container(settings, config)
    days = trading_days(container.bars, config)

    equity_by_day: dict[pd.Timestamp, float] = {}
    decisions_log: list[dict] = []
    num_trades = 0

    for day in days:
        # `day` is the bar's own (early, session-start) timestamp — fine for price
        # lookups since only one bar exists per calendar day, but too early a cutoff
        # for news: same-day articles published during market hours would be wrongly
        # excluded even though the day's own close (which we're deciding against) already
        # reflects that day's full session. Use end-of-day so news filtering matches.
        container.clock.now = day.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        state = await container.pipeline.run_cycle(config.tickers)

        summary = decision_summary(state)
        decisions_log.append({"date": day, "tickers": summary})
        num_trades += sum(1 for t in summary if t["executed"])

        equity_by_day[day] = container.broker.get_account().equity
        logger.info("%s: equity=%.2f", day.date(), equity_by_day[day])

    equity_curve = pd.Series(equity_by_day).sort_index()
    await container.db.dispose()
    return BacktestResult(
        equity_curve=equity_curve, decisions_log=decisions_log, num_trades=num_trades
    )
