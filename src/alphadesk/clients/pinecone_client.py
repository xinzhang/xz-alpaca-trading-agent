"""Thin wrapper around Pinecone: archives news-article embeddings per ticker."""

from typing import Any

from pinecone import Pinecone, ServerlessSpec

from alphadesk.config import Settings

EMBEDDING_DIM = 1536  # text-embedding-3-small


class PineconeNewsStore:
    def __init__(self, settings: Settings) -> None:
        self._client = Pinecone(api_key=settings.pinecone_api_key)
        self._index_name = settings.pinecone_index_name
        self._ensure_index(settings.pinecone_cloud, settings.pinecone_region)
        self._index = self._client.Index(self._index_name)

    def _ensure_index(self, cloud: str, region: str) -> None:
        existing = {idx.name for idx in self._client.list_indexes()}
        if self._index_name not in existing:
            self._client.create_index(
                name=self._index_name,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )

    def upsert_articles(
        self, ticker: str, articles: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
        if not articles:
            return
        vectors = [
            {
                "id": article["id"],
                "values": embedding,
                "metadata": {
                    "ticker": ticker,
                    "title": article["title"],
                    "url": article["url"],
                    "published_at": article["published_at"],
                },
            }
            for article, embedding in zip(articles, embeddings, strict=True)
        ]
        self._index.upsert(vectors=vectors, namespace=ticker)
