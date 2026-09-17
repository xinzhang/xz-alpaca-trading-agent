"""Replays the real 5-agent pipeline over a historical date range.

Uses Alpaca's own historical News API (not Tavily) for point-in-time-correct
sentiment input, and an in-memory simulated broker instead of real order submission.

    uv run python scripts/run_backtest.py --start 2026-06-01 --end 2026-09-01 \
        --tickers AAPL,NVDA,TSLA --initial-cash 50000
"""

import argparse
import asyncio
import logging
from datetime import date

from alphadesk.backtest.config import BacktestConfig
from alphadesk.backtest.report import report
from alphadesk.backtest.runner import run_backtest
from alphadesk.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument(
        "--tickers", default=None, help="Comma-separated, defaults to TICKERS in .env"
    )
    parser.add_argument("--initial-cash", type=float, default=50_000.0)
    parser.add_argument("--lookback-buffer-days", type=int, default=90)
    parser.add_argument("--name", default="backtest", help="Prefix for saved result files")
    return parser.parse_args()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args()
    settings = get_settings()
    tickers = (
        [t.strip().upper() for t in args.tickers.split(",")]
        if args.tickers
        else settings.ticker_list
    )

    config = BacktestConfig(
        tickers=tickers,
        start=args.start,
        end=args.end,
        initial_cash=args.initial_cash,
        lookback_buffer_days=args.lookback_buffer_days,
    )

    print(f"Backtesting {tickers} from {config.start} to {config.end} "
          f"with ${config.initial_cash:,.2f} starting cash...")
    result = await run_backtest(settings, config)
    report(result, run_name=args.name)


if __name__ == "__main__":
    asyncio.run(main())
