"""Publishes pipeline-cycle events to Redis so the dashboard can stream them live."""

import json
from typing import Any

import redis.asyncio as aioredis

CHANNEL = "alphadesk:events"


class EventBus:
    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"type": event_type, "payload": payload}, default=str)
        await self._redis.publish(CHANNEL, message)

    def subscribe(self):
        pubsub = self._redis.pubsub()
        return pubsub, CHANNEL

    async def close(self) -> None:
        await self._redis.close()
