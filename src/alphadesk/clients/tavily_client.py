"""Thin wrapper around Tavily: fetches recent news headlines per ticker."""

import hashlib
from typing import Any

from tavily import TavilyClient as _TavilyClient

from alphadesk.config import Settings


class TavilyNewsClient:
    def __init__(self, settings: Settings) -> None:
        self._client = _TavilyClient(api_key=settings.tavily_api_key)

    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
        response = self._client.search(
            query=f"{ticker} stock news",
            topic="news",
            search_depth="basic",
            max_results=max_results,
            days=2,
        )
        articles = []
        for result in response.get("results", []):
            article_id = hashlib.sha256(result["url"].encode()).hexdigest()[:32]
            articles.append(
                {
                    "id": article_id,
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "url": result["url"],
                    "published_at": result.get("published_date", ""),
                }
            )
        return articles
