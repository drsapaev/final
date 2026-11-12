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
        reconnect_backoff_base: float = 1.0,
    ) -> None:
        self.channel_prefix = channel_prefix
        self.redis_url = (
            redis_url or os.getenv("WS_REDIS_URL") or os.getenv("REDIS_URL") or ""
        )
        self.instance_id = instance_id or os.getenv("WS_INSTANCE_ID") or uuid4().hex
        self.enabled = bool(self.redis_url)

        # DISPLAYRELAY-BE-002 (audit PR #3961): bounded reconnect backoff
        # for a crashed listener; base delay in seconds, doubled per attempt.
        self._reconnect_backoff_base = reconnect_backoff_base

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
        await self._redis_client.publish(
            channel, json.dumps(envelope, ensure_ascii=False)
        )
        return True

    async def publish_ephemeral(self, logical_channel: str, payload: dict) -> bool:
        """Publish from short-lived event loops without creating a listener.

        ARQ outbox batches run inside ``asyncio.run`` on a worker thread. The
        regular ``publish`` path initializes a pub/sub listener tied to that
        temporary loop, so this one-shot publisher owns and closes its Redis
        client before the loop exits.
        """
        if not self.enabled:
            return False

        client = None
        try:
            if self._redis_mod is None:
                import redis.asyncio as redis_asyncio

                self._redis_mod = redis_asyncio

            client = self._redis_mod.from_url(
                self.redis_url,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            envelope = {
                "source": self.instance_id,
                "payload": payload,
            }
            await client.publish(
                self._channel(logical_channel),
                json.dumps(envelope, ensure_ascii=False),
            )
            return True
        except Exception as exc:
            if not self._warned_unavailable:
                logger.warning(
                    "Redis pub/sub publish unavailable: %s", type(exc).__name__
                )
                self._warned_unavailable = True
            return False
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception as exc:
                    logger.warning(
                        "Redis pub/sub publisher close failed: %s",
                        type(exc).__name__,
                    )

    async def subscribe(self, logical_channel: str, handler: Handler) -> bool:
        """Добавить обработчик канала.

        DISPLAYRELAY-BE-003 (audit PR #3961): возвращает честный статус —
        ``True`` только после успешного Redis SUBSCRIBE (или когда канал уже
        был подписан); ``False`` при сбое подписки/недоступном Redis.
        Вызывающий код решает, кэшировать ли обработчик.

        Follow-up #4035 (P1-остаток ревью): неудавшаяся подписка НЕ оставляет
        «фантомную» регистрацию обработчика. Раньше обработчик добавлялся ДО
        проверки готовности Redis и оставался в наборе при ``False``; повтор
        с тем же обработчиком видел ``was_added=False``, пропускал реальный
        Redis SUBSCRIBE и возвращал ``True`` — кэш успешной подписки без
        реальной подписки (воркер терял control-инвалидацию формата имён
        после даунгрейда приватности). Откат выполняется только когда
        регистрация добавлена ЭТИМ вызовом (``was_added``) — конкурентный
        владелец того же обработчика не затрагивается.
        """
        handlers = self._handlers[logical_channel]
        was_added = handler not in handlers
        handlers.add(handler)
        if not await self._ensure_ready():
            if was_added:
                handlers.discard(handler)
                if not handlers:
                    self._handlers.pop(logical_channel, None)
            return False

        assert self._pubsub is not None
        if was_added and len(handlers) == 1:
            try:
                await self._pubsub.subscribe(self._channel(logical_channel))
            except Exception as exc:
                handlers.discard(handler)
                if not handlers:
                    self._handlers.pop(logical_channel, None)
                logger.warning(
                    "Redis pub/sub subscription failed: %s", type(exc).__name__
                )
                return False
            else:
                # redis-py's listen() iterator exits immediately when the
                # PubSub has no channels. Start it only after the first
                # subscription is active, and restart it after an idle period.
                if self._listener_task is None or self._listener_task.done():
                    self._listener_task = asyncio.create_task(self._listen_loop())
        return True

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

                channel = (
                    raw_channel.decode()
                    if isinstance(raw_channel, bytes)
                    else str(raw_channel)
                )
                data = (
                    raw_data.decode() if isinstance(raw_data, bytes) else str(raw_data)
                )

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
            # DISPLAYRELAY-BE-002 (audit PR #3961): сбой листенера больше не
            # означает постоянную потерю кросс-воркерных событий для уже
            # подключённых табло — ограниченный reconnect с бэкоффом
            # восстанавливает pubsub и переподписывает живые каналы.
            await self._recover_listener()

    async def _recover_listener(self) -> None:
        """Ограниченное восстановление листенера (bounded backoff)."""
        for attempt in range(1, 6):
            delay = self._reconnect_backoff_base * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
            try:
                await self._reset_pubsub()
                await self._resubscribe_all()
                self._listener_task = asyncio.create_task(self._listen_loop())
                logger.info(
                    "Redis pub/sub listener recovered after %d attempt(s)", attempt
                )
                return
            except Exception as exc:
                logger.warning(
                    "Redis pub/sub recovery attempt %d failed: %s",
                    attempt,
                    exc,
                )
        logger.error(
            "Redis pub/sub recovery exhausted after %d attempts; "
            "cross-worker events stay unavailable until a new subscribe",
            5,
        )

    async def _reset_pubsub(self) -> None:
        """Пересоздать pubsub-соединение (старое могло умереть)."""
        self._pubsub = None
        if self._redis_client is not None:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None
        if not await self._ensure_ready():
            raise RuntimeError("redis pub/sub unavailable")

    async def _resubscribe_all(self) -> None:
        """Переподписать все каналы с живыми обработчиками."""
        assert self._pubsub is not None
        for logical_channel, handlers in list(self._handlers.items()):
            if handlers:
                await self._pubsub.subscribe(self._channel(logical_channel))
