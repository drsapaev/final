from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


Handler = Callable[[dict], Awaitable[None]]


class RedisPubSubBridge:
    """
    Lightweight Redis pub/sub bridge for cross-instance websocket broadcasts.

    Gracefully degrades to no-op when Redis or redis-py is unavailable.
    """

    def __init__(
        self,
        channel_prefix: str,
        redis_url: str | None = None,
        instance_id: str | None = None,
    ) -> None:
        self.channel_prefix = channel_prefix
        self.redis_url = (
            redis_url
            or os.getenv("WS_REDIS_URL")
            or os.getenv("REDIS_URL")
            or ""
        )
        self.instance_id = instance_id or os.getenv("WS_INSTANCE_ID") or uuid4().hex
        self.enabled = bool(self.redis_url)

        self._redis_mod = None
        self._redis_client = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._handlers: dict[str, set[Handler]] = defaultdict(set)
        self._init_lock = asyncio.Lock()
        self._warned_unavailable = False

    def _channel(self, logical_channel: str) -> str:
        return f"{self.channel_prefix}:{logical_channel}"

    async def publish(self, logical_channel: str, payload: dict) -> bool:
        if not await self._ensure_ready():
            return False

        assert self._redis_client is not None
        envelope = {
            "source": self.instance_id,
            "payload": payload,
        }
        channel = self._channel(logical_channel)
        await self._redis_client.publish(channel, json.dumps(envelope, ensure_ascii=False))
        return True

    async def subscribe(self, logical_channel: str, handler: Handler) -> None:
        self._handlers[logical_channel].add(handler)
        if not await self._ensure_ready():
            return

        assert self._pubsub is not None
        if len(self._handlers[logical_channel]) == 1:
            await self._pubsub.subscribe(self._channel(logical_channel))

    async def unsubscribe(self, logical_channel: str, handler: Handler) -> None:
        handlers = self._handlers.get(logical_channel)
        if not handlers:
            return
        handlers.discard(handler)
        if handlers:
            return

        self._handlers.pop(logical_channel, None)
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self._channel(logical_channel))

    async def _ensure_ready(self) -> bool:
        if not self.enabled:
            return False
        if self._pubsub is not None:
            return True

        async with self._init_lock:
            if self._pubsub is not None:
                return True

            try:
                if self._redis_mod is None:
                    import redis.asyncio as redis_asyncio

                    self._redis_mod = redis_asyncio

                self._redis_client = self._redis_mod.from_url(self.redis_url)
                self._pubsub = self._redis_client.pubsub()
                self._listener_task = asyncio.create_task(self._listen_loop())
                logger.info(
                    "Redis pub/sub bridge enabled: prefix=%s instance=%s",
                    self.channel_prefix,
                    self.instance_id[:8],
                )
                return True
            except Exception as exc:
                self.enabled = False
                if not self._warned_unavailable:
                    logger.warning("Redis pub/sub disabled: %s", exc)
                    self._warned_unavailable = True
                return False

    async def _listen_loop(self) -> None:
        assert self._pubsub is not None
        try:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue

                raw_channel = event.get("channel")
                raw_data = event.get("data")
                if not raw_channel or raw_data is None:
                    continue

                channel = raw_channel.decode() if isinstance(raw_channel, bytes) else str(raw_channel)
                data = raw_data.decode() if isinstance(raw_data, bytes) else str(raw_data)

                if not channel.startswith(f"{self.channel_prefix}:"):
                    continue
                logical_channel = channel[len(self.channel_prefix) + 1 :]

                try:
                    envelope = json.loads(data)
                except Exception:
                    continue

                if envelope.get("source") == self.instance_id:
                    continue

                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    continue

                handlers = list(self._handlers.get(logical_channel, set()))
                for handler in handlers:
                    try:
                        await handler(payload)
                    except Exception:
                        logger.exception(
                            "Redis pub/sub handler failed: channel=%s", logical_channel
                        )
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Redis pub/sub listener crashed")
