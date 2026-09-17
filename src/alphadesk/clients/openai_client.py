"""Thin wrapper around the OpenAI SDK: chat completion for decisions, embeddings for news."""

import json
from typing import Any

from openai import OpenAI

from alphadesk.config import Settings


class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._decision_model = settings.openai_decision_model
        self._embedding_model = settings.openai_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._embedding_model, input=texts)
        return [item.embedding for item in response.data]

    def decide(self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]) -> dict:
        response = self._client.chat.completions.create(
            model=self._decision_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "trade_decision", "schema": json_schema, "strict": True},
            },
            temperature=0.2,
        )
        return json.loads(response.choices[0].message.content)
