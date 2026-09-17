"""Composition root: the one place that constructs every client, agent, and service.

Keeping construction here (rather than scattered `__init__`s reaching for globals)
is what makes each agent/client independently testable with fakes.
"""

from dataclasses import dataclass

from alphadesk.agents.decision_agent import DecisionAgent
from alphadesk.agents.execution_agent import ExecutionAgent
from alphadesk.agents.risk_agent import RiskAgent
from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.agents.signal_agent import SignalAgent
from alphadesk.clients.alpaca_client import AlpacaClient
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.clients.pinecone_client import PineconeNewsStore
from alphadesk.clients.redis_bus import EventBus
from alphadesk.clients.tavily_client import TavilyNewsClient
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.pipeline import TradingPipeline
from alphadesk.scheduler import Scheduler


@dataclass(slots=True)
class Container:
    settings: Settings
    db: Database
    event_bus: EventBus
    alpaca: AlpacaClient
    pipeline: TradingPipeline
    scheduler: Scheduler


def build_container(settings: Settings) -> Container:
    db = Database(settings.database_url)
    event_bus = EventBus(settings.redis_url)

    alpaca = AlpacaClient(settings)
    openai = OpenAIClient(settings)
    pinecone = PineconeNewsStore(settings)
    tavily = TavilyNewsClient(settings)

    signal_agent = SignalAgent(db, event_bus, alpaca)
    risk_agent = RiskAgent(db, event_bus, alpaca, settings)
    sentiment_agent = SentimentAgent(db, event_bus, tavily, openai, pinecone)
    decision_agent = DecisionAgent(db, event_bus, openai)
    execution_agent = ExecutionAgent(db, event_bus, alpaca, settings)

    pipeline = TradingPipeline(
        signal_agent, risk_agent, sentiment_agent, decision_agent, execution_agent
    )
    scheduler = Scheduler(pipeline, alpaca, event_bus, settings)

    return Container(
        settings=settings, db=db, event_bus=event_bus, alpaca=alpaca, pipeline=pipeline,
        scheduler=scheduler,
    )
