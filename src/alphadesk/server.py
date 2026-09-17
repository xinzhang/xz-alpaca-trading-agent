"""FastAPI app: REST snapshot endpoints for the dashboard + a WebSocket that bridges
Redis pub/sub events to connected browser clients in real time.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from alphadesk.clients.alpaca_client import AlpacaClient
from alphadesk.clients.redis_bus import EventBus
from alphadesk.config import Settings, get_settings
from alphadesk.db.base import Database
from alphadesk.db.models import AgentLogEntry, Decision, PortfolioSnapshot
from alphadesk.scheduler import Scheduler

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings,
    db: Database,
    event_bus: EventBus,
    alpaca: AlpacaClient,
    scheduler: Scheduler,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.create_all()
        scheduler_task = asyncio.create_task(scheduler.run_forever())
        yield
        scheduler.stop()
        await scheduler_task
        await event_bus.close()
        await db.dispose()

    app = FastAPI(title="AlphaDesk-style Trading Agent", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "dry_run": settings.dry_run, "tickers": settings.ticker_list}

    @app.get("/api/account")
    async def account():
        snapshot = alpaca.get_account()
        return {
            "equity": snapshot.equity,
            "cash": snapshot.cash,
            "buying_power": snapshot.buying_power,
            "portfolio_value": snapshot.portfolio_value,
        }

    @app.get("/api/positions")
    async def positions():
        return [
            {
                "ticker": p.symbol,
                "qty": p.qty,
                "market_value": p.market_value,
                "avg_entry_price": p.avg_entry_price,
                "unrealized_pl": p.unrealized_pl,
            }
            for p in alpaca.get_positions().values()
        ]

    @app.get("/api/decisions")
    async def decisions(limit: int = 50):
        async with db.session() as session:
            result = await session.execute(
                select(Decision).order_by(Decision.ts.desc()).limit(limit)
            )
            rows = result.scalars().all()
        return [
            {
                "ts": row.ts,
                "ticker": row.ticker,
                "action": row.action,
                "confidence": row.confidence,
                "rationale": row.rationale,
                "risk_approved": row.risk_approved,
                "risk_reason": row.risk_reason,
                "executed": row.executed,
            }
            for row in rows
        ]

    @app.get("/api/logs")
    async def logs(limit: int = 100):
        async with db.session() as session:
            result = await session.execute(
                select(AgentLogEntry).order_by(AgentLogEntry.ts.desc()).limit(limit)
            )
            rows = result.scalars().all()
        return [
            {
                "ts": row.ts,
                "node": row.node,
                "ticker": row.ticker,
                "message": row.message,
                "payload": row.payload,
            }
            for row in rows
        ]

    @app.get("/api/portfolio_history")
    async def portfolio_history(limit: int = 200):
        async with db.session() as session:
            result = await session.execute(
                select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(limit)
            )
            rows = result.scalars().all()
        return [
            {
                "ts": row.ts,
                "equity": row.equity,
                "peak_equity": row.peak_equity,
                "drawdown_pct": row.drawdown_pct,
            }
            for row in reversed(rows)
        ]

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        pubsub, channel = event_bus.subscribe()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                await websocket.send_text(message["data"])
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return app


def build_default_app() -> FastAPI:
    """Used by `uvicorn alphadesk.server:build_default_app --factory` for local dev."""
    from alphadesk.wiring import build_container

    container = build_container(get_settings())
    return create_app(
        container.settings, container.db, container.event_bus, container.alpaca, container.scheduler
    )
