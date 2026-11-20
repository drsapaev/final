"""Atomic storage for scoped one-time phone verification records.

The shared Redis implementation is mandatory outside explicit test mode.
Records contain only a keyed code digest and identity bindings; phone numbers
and one-time codes are never present in Redis keys or stored values.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
from typing import Any

from app.core.config import settings


class PhoneStoreUnavailable(RuntimeError):
    """The shared verification store is unavailable or inconsistent."""


def _owner_matches(record: dict[str, Any], actor: tuple[str, str, str] | None, admin: bool) -> bool:
    if "owner" not in record:
        return False
    owner = record.get("owner")
    if admin and owner is None:
        return True
    return actor is not None and isinstance(owner, list) and owner == list(actor)


class MemoryPhoneStore:
    """TESTING-only atomic store; instances may share one object in tests."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, float]] = {}
        self._leases: dict[str, tuple[str, float]] = {}
        self._cooldowns: dict[str, float] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._ip_budgets: dict[str, tuple[int, float]] = {}
        self._lock = threading.RLock()

    def consume_ip_verify_budget(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            count, until = self._ip_budgets.get(key, (0, 0))
            if until <= now:
                count, until = 0, now + 60
            if count >= 30:
                return False
            self._ip_budgets[key] = (count + 1, until)
            return True

    @staticmethod
    def _alive(item: tuple[str, float] | None) -> bool:
        return bool(item and item[1] > time.monotonic())

    def reserve(self, key: str, nonce: str, lease_ttl: int, cooldown: int) -> bool:
        with self._lock:
            now = time.monotonic()
            if self._cooldowns.get(key, 0) > now or self._alive(self._leases.get(key)):
                return False
            self._leases[key] = (nonce, now + lease_ttl)
            self._cooldowns[key] = now + cooldown
            return True

    def release(self, key: str, nonce: str) -> None:
        with self._lock:
            item = self._leases.get(key)
            if self._alive(item) and item[0] == nonce:
                del self._leases[key]

    def publish(self, key: str, nonce: str, payload: str, ttl: int, cooldown: int,
                lifetime: int = 300, lease_ttl: int = 90) -> bool:
        with self._lock:
            item = self._leases.get(key)
            if not self._alive(item) or item[0] != nonce or ttl <= 0:
                return False
            now = time.monotonic()
            deadline = min(now + ttl, item[1] + lifetime - lease_ttl)
            if deadline <= now:
                return False
            self._records[key] = (payload, deadline)
            self._cooldowns[key] = time.monotonic() + cooldown
            del self._leases[key]
            return True

    def _load(self, key: str) -> dict[str, Any] | None:
        item = self._records.get(key)
        if not self._alive(item):
            self._records.pop(key, None)
            return None
        try:
            record = json.loads(item[0])
            if not isinstance(record, dict) or type(record.get("version")) is not int or record["version"] != 1:
                raise ValueError("invalid verification record")
            return record
        except (ValueError, TypeError):
            self._records.pop(key, None)
            return None

    def verify(self, key: str, nonce: str, digest: str, actor: tuple[str, str, str] | None,
               admin: bool, internal: bool, remove: bool, max_attempts: int,
               failure_budget: int = 10, failure_window: int = 3600) -> tuple[str, dict[str, Any] | None]:
        with self._lock:
            record = self._load(key)
            if record is None or record.get("nonce") != nonce or (not internal and not _owner_matches(record, actor, admin)):
                return "missing", None
            if record.get("verified") is True:
                return "missing", None
            count, until = self._failures.get(key, (0, 0))
            if until <= time.monotonic():
                count, until = 0, time.monotonic() + failure_window
            if count >= failure_budget:
                return "locked", {"attempts": max_attempts}
            attempts = record.get("attempts")
            if type(attempts) is not int or attempts < 0:
                self._records.pop(key, None)
                return "missing", None
            if attempts >= max_attempts:
                return "locked", {"attempts": attempts}
            attempts += 1
            if not isinstance(record.get("digest"), str):
                self._records.pop(key, None)
                return "missing", None
            if not hmac.compare_digest(record["digest"], digest):
                self._failures[key] = (count + 1, until)
                record["attempts"] = attempts
                self._records[key] = (json.dumps(record), self._records[key][1])
                return "invalid", {"attempts": attempts}
            remaining_ttl_ms = int((self._records[key][1] - time.monotonic()) * 1000)
            if remaining_ttl_ms <= 0:
                self._records.pop(key, None)
                return "missing", None
            if remove:
                self._records.pop(key, None)
            else:
                record["verified"] = True
                self._records[key] = (json.dumps(record), self._records[key][1])
            self._failures.pop(key, None)
            record["_remaining_ttl_ms"] = remaining_ttl_ms
            return "ok", record

    def status(self, key: str, actor: tuple[str, str, str] | None, admin: bool, internal: bool = False) -> dict[str, Any] | None:
        with self._lock:
            record = self._load(key)
            return record if record is not None and (internal or _owner_matches(record, actor, admin)) else None

    def cancel(self, key: str, actor: tuple[str, str, str], admin: bool) -> bool:
        with self._lock:
            record = self._load(key)
            if record is None or not _owner_matches(record, actor, admin):
                return False
            self._records.pop(key, None)
            return True

    def statistics(self) -> list[dict[str, Any]]:
        with self._lock:
            return [record for key in list(self._records) if (record := self._load(key)) is not None]


_AUTH_LUA = r"""
local raw = redis.call('GET', KEYS[1])
if not raw then return nil end
local ttl = redis.call('PTTL', KEYS[1])
if ttl <= 0 then redis.call('DEL', KEYS[1]); return nil end
local ok, record = pcall(cjson.decode, raw)
if not ok or type(record) ~= 'table' or record.version ~= 1 then
  redis.call('DEL', KEYS[1]); return nil
end
local owner = record.owner
if ARGV[1] ~= 'internal' then
  if ARGV[1] == 'admin' and owner == cjson.null then
    -- Only explicitly unbound administrator records are shareable.
  elseif type(owner) ~= 'table' or #owner ~= 3 or owner[1] ~= ARGV[2] or owner[2] ~= ARGV[3] or owner[3] ~= ARGV[4] then
    return nil
  end
end
"""


class RedisPhoneStore:
    """Cross-worker store: every owner check and mutation is one Redis script."""

    def __init__(self, client=None) -> None:
        if client is None:
            import redis

            url = os.getenv("REDIS_URL", "").strip() or settings.ARQ_REDIS_URL
            client = redis.Redis.from_url(
                url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
            )
            client.ping()
        self._client = client

    def _eval(self, script: str, keys: list[str], *args: Any):
        try:
            return self._client.eval(script, len(keys), *keys, *args)
        except Exception as exc:
            raise PhoneStoreUnavailable("Phone verification storage unavailable") from exc

    def consume_ip_verify_budget(self, key: str) -> bool:
        script = """
        local previous = redis.call('GET', KEYS[1])
        if previous and (not string.match(previous, '^%d+$') or redis.call('PTTL', KEYS[1]) <= 0) then
          return -1
        end
        if (tonumber(previous) or 0) >= 30 then return 0 end
        local count = redis.call('INCR', KEYS[1])
        if count == 1 then redis.call('EXPIRE', KEYS[1], 60) end
        return 1
        """
        result = self._eval(script, [key])
        if result not in (0, 1):
            raise PhoneStoreUnavailable("Invalid verification budget")
        return bool(result)

    @staticmethod
    def _keys(key: str) -> list[str]:
        return [f"{key}:record", f"{key}:lease", f"{key}:cooldown", f"{key}:failures"]

    def reserve(self, key: str, nonce: str, lease_ttl: int, cooldown: int) -> bool:
        script = """
        if redis.call('EXISTS', KEYS[2]) == 1 or redis.call('EXISTS', KEYS[3]) == 1 then return 0 end
        redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
        redis.call('SET', KEYS[3], '1', 'EX', ARGV[3]); return 1
        """
        return bool(self._eval(script, self._keys(key), nonce, lease_ttl, cooldown))

    def release(self, key: str, nonce: str) -> None:
        self._eval("if redis.call('GET', KEYS[2]) == ARGV[1] then return redis.call('DEL', KEYS[2]) end return 0", self._keys(key), nonce)

    def publish(self, key: str, nonce: str, payload: str, ttl: int, cooldown: int,
                lifetime: int = 300, lease_ttl: int = 90) -> bool:
        script = """
        if redis.call('GET', KEYS[2]) ~= ARGV[1] or tonumber(ARGV[3]) <= 0 then return 0 end
        local remaining_lease_ms = redis.call('PTTL', KEYS[2])
        local remaining_ms = math.min(tonumber(ARGV[3]) * 1000,
                                      remaining_lease_ms + (tonumber(ARGV[5]) - tonumber(ARGV[6])) * 1000)
        if remaining_lease_ms <= 0 or remaining_ms <= 0 then return 0 end
        redis.call('SET', KEYS[1], ARGV[2], 'PX', remaining_ms)
        redis.call('SET', KEYS[3], '1', 'EX', ARGV[4])
        redis.call('DEL', KEYS[2]); return 1
        """
        return bool(self._eval(script, self._keys(key), nonce, payload, ttl, cooldown, lifetime, lease_ttl))

    @staticmethod
    def _args(actor: tuple[str, str, str] | None, admin: bool, internal: bool = False) -> list[str]:
        return ["internal" if internal else "admin" if admin else "owner", *(actor or ("", "", ""))]

    def verify(self, key: str, nonce: str, digest: str, actor: tuple[str, str, str] | None,
               admin: bool, internal: bool, remove: bool, max_attempts: int,
               failure_budget: int = 10, failure_window: int = 3600) -> tuple[str, dict[str, Any] | None]:
        script = _AUTH_LUA + """
        if record.verified == true or record.nonce ~= ARGV[8] then return nil end
        local previous = redis.call('GET', KEYS[2])
        if previous and (not string.match(previous, '^%d+$') or redis.call('PTTL', KEYS[2]) <= 0) then return nil end
        local failures = tonumber(previous) or 0
        if failures >= tonumber(ARGV[9]) then return cjson.encode({outcome='locked', attempts=tonumber(ARGV[6])}) end
        local attempts = record.attempts
        if type(attempts) ~= 'number' or attempts < 0 or attempts ~= math.floor(attempts) or type(record.digest) ~= 'string' then
          redis.call('DEL', KEYS[1]); return nil
        end
        if attempts >= tonumber(ARGV[6]) then return cjson.encode({outcome='locked', attempts=attempts}) end
        attempts = attempts + 1
        if record.digest ~= ARGV[5] then
          local count = redis.call('INCR', KEYS[2])
          if count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[10]) end
          record.attempts = attempts; redis.call('SET', KEYS[1], cjson.encode(record), 'PX', ttl)
          return cjson.encode({outcome='invalid', attempts=attempts})
        end
        if ARGV[7] == '1' then redis.call('DEL', KEYS[1])
        else record.verified = true; redis.call('SET', KEYS[1], cjson.encode(record), 'PX', ttl) end
        redis.call('DEL', KEYS[2])
        return cjson.encode({outcome='ok', record=record, remaining_ttl_ms=ttl})
        """
        keys = self._keys(key)
        raw = self._eval(script, [keys[0], keys[3]], *self._args(actor, admin, internal), digest, max_attempts, int(remove), nonce, failure_budget, failure_window)
        if raw is None:
            return "missing", None
        try:
            result = json.loads(raw)
            outcome = result["outcome"]
            record = result.get("record", {"attempts": result.get("attempts")})
            if outcome == "ok":
                ttl = result.get("remaining_ttl_ms")
                if type(ttl) is not int or ttl <= 0 or not isinstance(record, dict):
                    raise ValueError("invalid verification TTL")
                record["_remaining_ttl_ms"] = ttl
            return outcome, record
        except (ValueError, KeyError, TypeError) as exc:
            raise PhoneStoreUnavailable("Invalid verification storage result") from exc

    def status(self, key: str, actor: tuple[str, str, str] | None, admin: bool, internal: bool = False) -> dict[str, Any] | None:
        raw = self._eval(_AUTH_LUA + " return raw", [self._keys(key)[0]], *self._args(actor, admin, internal))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise PhoneStoreUnavailable("Invalid verification storage result") from exc

    def cancel(self, key: str, actor: tuple[str, str, str], admin: bool) -> bool:
        return bool(self._eval(_AUTH_LUA + " return redis.call('DEL', KEYS[1])", [self._keys(key)[0]], *self._args(actor, admin)))

    def statistics(self) -> list[dict[str, Any]]:
        """Bounded admin-only diagnostic; never return a misleading partial count."""
        try:
            records = []
            for key in self._client.scan_iter(match="phonever:{*}:record", count=100):
                if len(records) >= 10000:
                    raise PhoneStoreUnavailable("Verification statistics exceed limit")
                raw = self._client.get(key)
                if raw is not None:
                    record = json.loads(raw)
                    if not isinstance(record, dict) or record.get("version") != 1:
                        raise PhoneStoreUnavailable("Invalid verification record")
                    records.append(record)
            return records
        except PhoneStoreUnavailable:
            raise
        except Exception as exc:
            raise PhoneStoreUnavailable("Phone verification storage unavailable") from exc
