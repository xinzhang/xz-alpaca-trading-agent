"""Runs exactly one pipeline cycle immediately, ignoring market hours.

The production scheduler (`alphadesk.scheduler.Scheduler`) deliberately skips cycles
while the market is closed — this script exists only for manual testing/debugging, so
you can validate the pipeline end-to-end without waiting for market hours.

    uv run python scripts/run_once.py
"""

import asyncio
import json
import logging

from alphadesk.config import get_settings
from alphadesk.pipeline import decision_summary
from alphadesk.wiring import build_container


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    settings = get_settings()
    container = build_container(settings)

    print(f"Market open: {container.alpaca.is_market_open()}")
    print(f"DRY_RUN: {settings.dry_run}")
    print(f"Tickers: {settings.ticker_list}")

    state = await container.pipeline.run_cycle(settings.ticker_list)
    print(json.dumps(decision_summary(state), indent=2, default=str))

    await container.event_bus.close()
    await container.db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
