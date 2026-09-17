"""Composition root for a backtest run — mirrors `alphadesk.wiring.build_container`,
but wires the real agents to simulated/historical/null clients instead of live ones.

Reuses the real `Settings` object (loaded from `.env`, so it has valid Alpaca/OpenAI
keys) via `model_copy(update=...)` for the handful of fields that mean something
different in a backtest: `dry_run` is forced False (a backtest with no simulated fills
tests nothing), and `tickers` is overridden to the backtest's own ticker list.
"""

from dataclasses import dataclass

import pandas as pd

from alphadesk.agents.decision_agent import DecisionAgent
from alphadesk.agents.execution_agent import ExecutionAgent
from alphadesk.agents.risk_agent import RiskAgent
from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.agents.signal_agent import SignalAgent
from alphadesk.backtest.clock import SimulatedClock
from alphadesk.backtest.config import BacktestConfig
from alphadesk.backtest.data_loader import load_historical_bars, load_historical_news
from alphadesk.backtest.historical_news import HistoricalNewsClient
from alphadesk.backtest.null_clients import NullEventBus, NullPineconeStore
from alphadesk.backtest.simulated_broker import SimulatedBroker
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.pipeline import TradingPipeline


@dataclass(slots=True)
class BacktestContainer:
    clock: SimulatedClock
    broker: SimulatedBroker
    db: Database
    pipeline: TradingPipeline
    bars: dict[str, pd.DataFrame]


async def build_backtest_container(settings: Settings, config: BacktestConfig) -> BacktestContainer:
    backtest_settings = settings.model_copy(
        update={"tickers": ",".join(config.tickers), "dry_run": False}
    )

    bars = load_historical_bars(settings, config)
    news = load_historical_news(settings, config)

    clock = SimulatedClock(now=pd.Timestamp(config.start, tz="UTC"))
    broker = SimulatedBroker(clock, bars, config.initial_cash)
    news_client = HistoricalNewsClient(clock, news)
    openai = OpenAIClient(settings)
    pinecone = NullPineconeStore()
    event_bus = NullEventBus()

    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_all()

    signal_agent = SignalAgent(db, event_bus, broker)
    risk_agent = RiskAgent(db, event_bus, broker, backtest_settings)
    sentiment_agent = SentimentAgent(db, event_bus, news_client, openai, pinecone)
    decision_agent = DecisionAgent(db, event_bus, openai)
    execution_agent = ExecutionAgent(db, event_bus, broker, backtest_settings)

    pipeline = TradingPipeline(
        signal_agent, risk_agent, sentiment_agent, decision_agent, execution_agent
    )

    return BacktestContainer(clock=clock, broker=broker, db=db, pipeline=pipeline, bars=bars)
