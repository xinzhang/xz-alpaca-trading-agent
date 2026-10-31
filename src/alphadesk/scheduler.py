"""Runs the trading pipeline on a fixed interval, only while the market is open.

A failed cycle is logged and swallowed rather than crashing the process — a transient
API error on one 15-minute tick should not take the whole agent down.

`run_now` triggers a cycle on demand regardless of market hours (against the latest
bars, i.e. the last close when the market is shut); orders are only placed if the
market is open.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from alphadesk.clients.alpaca_client import AlpacaClient
from alphadesk.clients.redis_bus import EventBus
from alphadesk.config import Settings
from alphadesk.pipeline import TradingPipeline, decision_summary

logger = logging.getLogger(__name__)


class CycleInProgressError(RuntimeError):
    pass


class Scheduler:
    def __init__(
        self,
        pipeline: TradingPipeline,
        alpaca: AlpacaClient,
        event_bus: EventBus,
        settings: Settings,
    ) -> None:
        self._pipeline = pipeline
        self._alpaca = alpaca
        self._event_bus = event_bus
        self._settings = settings
        self._stopped = asyncio.Event()
        self._cycle_lock = asyncio.Lock()

    async def run_forever(self) -> None:
        interval_s = self._settings.cycle_interval_minutes * 60
        while not self._stopped.is_set():
            try:
                if self._alpaca.is_market_open():
                    await self._run_cycle_once()
                else:
                    logger.info("market closed, skipping cycle")
            except Exception:  # noqa: BLE001 - one bad cycle must not kill the scheduler
                logger.exception("pipeline cycle failed")

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopped.wait(), timeout=interval_s)

    async def run_now(self) -> dict[str, Any]:
        if self._cycle_lock.locked():
            raise CycleInProgressError("a cycle is already running")
        market_open = await asyncio.to_thread(self._alpaca.is_market_open)
        tickers = await self._run_cycle_once(orders_enabled=market_open)
        return {
            "ts": datetime.now(UTC),
            "market_open": market_open,
            "orders_enabled": market_open,
            "tickers": tickers,
        }

    async def _run_cycle_once(self, orders_enabled: bool = True) -> list[dict]:
        async with self._cycle_lock:
            state = await self._pipeline.run_cycle(
                self._settings.ticker_list, orders_enabled=orders_enabled
            )
        summary = decision_summary(state)
        await self._event_bus.publish("cycle_complete", {"tickers": summary})
        return summary

    def stop(self) -> None:
        self._stopped.set()
