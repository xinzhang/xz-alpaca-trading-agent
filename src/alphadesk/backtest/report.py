"""Prints a summary and saves the equity curve + decision log to `backtest_results/`."""

import json
from pathlib import Path

from alphadesk.backtest.metrics import compute_metrics
from alphadesk.backtest.runner import BacktestResult

RESULTS_DIR = Path("backtest_results")


def report(result: BacktestResult, run_name: str) -> None:
    metrics = compute_metrics(result.equity_curve, result.num_trades)

    print(f"\nBacktest period: {result.equity_curve.index[0].date()} to "
          f"{result.equity_curve.index[-1].date()} ({len(result.equity_curve)} trading days)")
    print(f"Starting equity: ${metrics.start_equity:,.2f}")
    print(f"Ending equity:   ${metrics.end_equity:,.2f}")
    print(f"Total return:    {metrics.total_return_pct:.2%}")
    print(f"Annualized Sharpe: {metrics.annualized_sharpe:.3f}")
    print(f"Max drawdown:    {metrics.max_drawdown_pct:.2%}")
    print(f"Number of trades executed: {metrics.num_trades}")

    RESULTS_DIR.mkdir(exist_ok=True)
    equity_path = RESULTS_DIR / f"{run_name}_equity.csv"
    result.equity_curve.to_csv(equity_path, header=["equity"])
    print(f"\nSaved equity curve: {equity_path}")

    decisions_path = RESULTS_DIR / f"{run_name}_decisions.jsonl"
    with decisions_path.open("w") as f:
        for row in result.decisions_log:
            f.write(json.dumps(row, default=str) + "\n")
    print(f"Saved decisions log: {decisions_path}")
