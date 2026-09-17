"""Runs the trading pipeline on a fixed interval, only while the market is open.

A failed cycle is logged and swallowed rather than crashing the process — a transient
API error on one 15-minute tick should not take the whole agent down.
"""

import asyncio
import contextlib
import logging

from alphadesk.clients.alpaca_client import AlpacaClient
from alphadesk.clients.redis_bus import EventBus
from alphadesk.config import Settings
from alphadesk.pipeline import TradingPipeline, decision_summary

logger = logging.getLogger(__name__)


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

    async def _run_cycle_once(self) -> None:
        state = await self._pipeline.run_cycle(self._settings.ticker_list)
        await self._event_bus.publish("cycle_complete", {"tickers": decision_summary(state)})

    def stop(self) -> None:
        self._stopped.set()
