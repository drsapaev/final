"""Short-lived references to invitations addressed to a display profile."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.models.online_queue import DailyQueue

DEFAULT_CALL_DURATION = 30
MAX_CALL_DURATION = 300


def utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def display_destination(queue: DailyQueue) -> tuple[str, str | None, str]:
    """Resolve an invitation and its queue row from the same daily assignment."""
    cabinet = getattr(queue, "cabinet_number", None)
    if getattr(queue, "queue_resource_id", None) is not None:
        resource = queue.queue_resource
        return (
            resource.display_name if resource else "Ресурс очереди",
            cabinet or (resource.default_cabinet if resource else None),
            queue.queue_tag or "Специалист",
        )

    doctor = queue.specialist
    return (
        doctor.user.full_name if doctor and doctor.user else "Врач",
        cabinet or (doctor.cabinet if doctor else None),
        doctor.specialty if doctor else "Специалист",
    )


@dataclass(frozen=True, slots=True)
class DisplayCallReference:
    event_id: str
    issued_at: str
    expires_at: str
    queue_id: int
    queue_entry_id: int
    called_at: str
    preserve_cabinet: bool = False
    cabinet: str | None = None

    @property
    def order(self) -> tuple[str, str]:
        return self.issued_at, self.event_id

    def has_expired(self, now: datetime) -> bool:
        return datetime.fromisoformat(self.expires_at) <= now

    def matches(self, queue_id: int, entry, now: datetime) -> bool:
        return (
            self.queue_id == queue_id
            and self.queue_entry_id == entry.id
            and entry.status == "called"
            and entry.called_at is not None
            and utc_timestamp(entry.called_at) == self.called_at
            and not self.has_expired(now)
        )


_REMEMBER_CALL = """
local previous = redis.call('GET', KEYS[1])
local incoming = cjson.decode(ARGV[1])
if previous then
    local saved = cjson.decode(previous)
    if saved.issued_at > incoming.issued_at or
        (saved.issued_at == incoming.issued_at and saved.event_id >= incoming.event_id) then
        return 0
    end
end
redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
return 1
"""


class DisplayCallStore:
    def __init__(self, redis_url: str | None):
        self._redis = (
            Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            if redis_url
            else None
        )
        self._local: dict[str, DisplayCallReference] = {}

    @staticmethod
    def _key(board_name: str) -> str:
        return f"display_ws:latest_call:{board_name}"

    async def remember(self, board_name: str, call: DisplayCallReference) -> bool:
        now = datetime.now(UTC)
        if call.has_expired(now):
            return False

        # Keep the ordering watermark for the maximum presentation window.
        # A delayed older event with a longer duration cannot replace it.
        retain_until = datetime.fromisoformat(call.issued_at) + timedelta(
            seconds=MAX_CALL_DURATION
        )
        ttl_ms = max(1, int((retain_until - now).total_seconds() * 1000))
        if self._redis is not None:
            result = await self._redis.eval(
                _REMEMBER_CALL,
                1,
                self._key(board_name),
                json.dumps(asdict(call)),
                ttl_ms,
            )
            return bool(result)

        for name, saved in tuple(self._local.items()):
            if (
                datetime.fromisoformat(saved.issued_at)
                + timedelta(seconds=MAX_CALL_DURATION)
                <= now
            ):
                self._local.pop(name)
        previous = self._local.get(board_name)
        if previous is not None and previous.order >= call.order:
            return False
        self._local[board_name] = call
        return True

    async def latest(self, board_name: str) -> DisplayCallReference | None:
        if self._redis is not None:
            value = await self._redis.get(self._key(board_name))
            return DisplayCallReference(**json.loads(value)) if value else None
        return self._local.get(board_name)
