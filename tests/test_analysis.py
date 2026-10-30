"""SymbolAnalyzer runs the real agents end-to-end against fakes, and must only report —
never submit an order, write an agent log, or publish to the live feed.
"""

import pandas as pd
from sqlalchemy import func, select

from alphadesk.agents.decision_agent import DecisionAgent
from alphadesk.agents.risk_agent import RiskAgent
from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.agents.signal_agent import SignalAgent
from alphadesk.analysis import SymbolAnalyzer
from alphadesk.backtest.null_clients import NullPineconeStore
from alphadesk.clients.alpaca_client import AccountSnapshot
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.db.models import AgentLogEntry, PortfolioSnapshot


class _FakeBroker:
    def get_recent_bars(self, symbol: str, lookback_bars: int = 100) -> pd.DataFrame:
        if symbol == "NODATA":
            return pd.DataFrame()
        return pd.DataFrame({"close": [100.0 + i * 0.1 for i in range(60)]})

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            equity=100_000, cash=100_000, buying_power=100_000, portfolio_value=100_000
        )

    def get_positions(self) -> dict:
        return {}

    def submit_market_order(self, *args, **kwargs):
        raise AssertionError("analysis must never submit an order")


class _FakeNews:
    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict]:
        return [{"id": "1", "title": f"{ticker} beats earnings", "content": "...",
                 "url": "https://example.com/1", "published_at": "2026-10-30"}]


class _FakeOpenAI:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def decide(self, system_prompt: str, user_prompt: str, json_schema: dict) -> dict:
        props = json_schema["properties"]
        if "label" in props:
            return {"rationale": "earnings beat", "label": "bullish", "score": 0.6}
        if "action" in props:
            return {"action": "BUY", "confidence": 0.7, "rationale": "uptrend + good news",
                    "target_notional": 5_000}
        return {"headline": "Moderate BUY", "summary": "...", "bull_case": ["trend"],
                "bear_case": ["overbought"], "key_risks": ["intraday noise"],
                "what_would_change_the_call": ["bad news"]}


class _RecordingBus:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def publish(self, event_type: str, payload: dict) -> None:
        self.events.append(event_type)


async def _build() -> tuple[SymbolAnalyzer, Database, _RecordingBus]:
    settings = Settings(
        _env_file=None, ALPACA_API_KEY="k", ALPACA_SECRET_KEY="s", OPENAI_API_KEY="k",
        PINECONE_API_KEY="k", TAVILY_API_KEY="k",
    )
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_all()
    bus, broker, openai = _RecordingBus(), _FakeBroker(), _FakeOpenAI()
    analyzer = SymbolAnalyzer(
        settings,
        SignalAgent(db, bus, broker),
        RiskAgent(db, bus, broker, settings),
        SentimentAgent(db, bus, _FakeNews(), openai, NullPineconeStore()),
        DecisionAgent(db, bus, openai),
        openai,
    )
    return analyzer, db, bus


async def test_analysis_reports_every_agent_without_side_effects():
    analyzer, db, bus = await _build()

    result = await analyzer.analyze("AAPL")

    assert result is not None
    assert result["signal"]["observations"]
    assert result["risk"]["observations"]
    assert result["sentiment"]["rationale"] == "earnings beat"
    assert result["decision"]["action"] == "BUY"
    assert "Ticker: AAPL" in result["decision"]["prompt"]
    assert result["risk_check"]["would_trade"] is True
    assert result["risk_check"]["approved_notional"] == 5_000
    assert result["summary"]["headline"] == "Moderate BUY"

    assert bus.events == []
    async with db.session() as session:
        for model in (AgentLogEntry, PortfolioSnapshot):
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0


async def test_analysis_returns_none_without_market_data():
    analyzer, _, _ = await _build()
    assert await analyzer.analyze("NODATA") is None
