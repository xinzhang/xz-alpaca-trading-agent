"""Interfaces SentimentAgent depends on. `TavilyNewsClient`/`PineconeNewsStore` (live)
and their backtest equivalents (`HistoricalNewsClient`/`NullPineconeStore`) both satisfy
these structurally, so SentimentAgent runs unmodified in either context.
"""

from typing import Any, Protocol


class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class NewsSource(Protocol):
    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict[str, Any]]: ...


class VectorStore(Protocol):
    def upsert_articles(
        self, ticker: str, articles: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None: ...

    def query_recent(
        self, ticker: str, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]: ...
