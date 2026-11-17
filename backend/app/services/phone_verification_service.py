"""Session-bound phone verification with cross-worker atomic storage."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import threading
import time
from datetime import UTC, datetime
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.services.phone_verification_store import (
    MemoryPhoneStore,
    PhoneStoreUnavailable,
    RedisPhoneStore,
)
from app.services.sms_providers import SMSProviderType, get_sms_manager

logger = logging.getLogger(__name__)


def _missing() -> dict[str, Any]:
    return {"success": False, "error": "Код не найден или истек", "error_code": "CODE_NOT_FOUND"}


def _identity(actor_id: int | None, actor_epoch: int | None, actor_jti: str | None) -> tuple[str, str, str] | None:
    if type(actor_id) is not int or actor_id <= 0 or type(actor_epoch) is not int or actor_epoch < 0 or not isinstance(actor_jti, str) or not actor_jti:
        return None
    return str(actor_id), str(actor_epoch), actor_jti


class PhoneVerificationService:
    """Store OTP proofs in Redis; the in-memory backend is for tests only."""

    def __init__(self, store: MemoryPhoneStore | RedisPhoneStore | None = None):
        self.sms_manager = get_sms_manager()
        self._store = store
        self._store_lock = threading.Lock()
        self.code_length = 6
        self.code_ttl_minutes = 5
        self.max_attempts = 3
        self.rate_limit_minutes = 1

    def _get_store(self) -> MemoryPhoneStore | RedisPhoneStore:
        if self._store is None:
            with self._store_lock:
                if self._store is None:
                    if os.getenv("TESTING", "").strip() == "1" and not settings.is_production:
                        self._store = MemoryPhoneStore()
                    else:
                        try:
                            self._store = RedisPhoneStore()
                        except Exception as exc:
                            logger.error("Phone verification storage unavailable: %s", type(exc).__name__)
                            raise PhoneStoreUnavailable("Phone verification storage unavailable") from exc
        return self._store

    def generate_verification_code(self) -> str:
        return "".join(str(secrets.randbelow(10)) for _ in range(self.code_length))

    @staticmethod
    def _mac(message: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _get_code_key(self, phone: str, purpose: str = "verification") -> str:
        # Curly braces keep the record, lease and cooldown in the same Redis
        # Cluster slot; neither the phone nor the code is exposed in the key.
        fingerprint = self._mac(json.dumps(["phone-verification-key-v1", purpose, phone], separators=(",", ":")))
        return f"phonever:{{{fingerprint}}}"

    def _code_digest(self, key: str, nonce: str, code: str) -> str:
        return self._mac(json.dumps(["phone-verification-code-v1", key, nonce, code], separators=(",", ":")))

    def consume_ip_verify_budget(self, client_ip: str) -> bool:
        """Bound password-reset guesses per trusted client IP across workers."""
        if not isinstance(client_ip, str) or not client_ip:
            raise PhoneStoreUnavailable("Invalid verification client")
        digest = self._mac(json.dumps(["phone-reset-verify-ip-v1", client_ip], separators=(",", ":")))
        return self._get_store().consume_ip_verify_budget(f"phonever:reset-ip:{digest}")

    async def send_verification_code(
        self,
        phone: str,
        purpose: str = "verification",
        provider_type: SMSProviderType | None = None,
        custom_message: str | None = None,
        account_binding: tuple[int, int] | None = None,
        owner_binding: tuple[int, int, str] | None = None,
    ) -> dict[str, Any]:
        """Reserve a send across workers, deliver outside locks, then publish."""
        if custom_message is not None and "{code}" not in custom_message:
            return {"success": False, "error": "Текст SMS должен содержать {code}", "error_code": "INVALID_CUSTOM_MESSAGE"}
        allow_mock = os.getenv("TESTING", "").strip() == "1" and not settings.is_production
        selected_provider = provider_type or getattr(self.sms_manager, "default_provider", None)
        if not allow_mock and selected_provider == SMSProviderType.MOCK:
            raise PhoneStoreUnavailable("SMS provider unavailable")
        owner = _identity(*owner_binding) if isinstance(owner_binding, tuple) and len(owner_binding) == 3 else None
        if owner_binding is not None and owner is None:
            raise PhoneStoreUnavailable("Invalid verification owner")
        if account_binding is not None and (
            not isinstance(account_binding, tuple) or len(account_binding) != 2
            or type(account_binding[0]) is not int or account_binding[0] <= 0
            or type(account_binding[1]) is not int or account_binding[1] < 0
        ):
            raise PhoneStoreUnavailable("Invalid verification account binding")

        key = self._get_code_key(phone, purpose)
        lease_nonce = secrets.token_urlsafe(24)
        published = False
        store = None
        try:
            store = await run_in_threadpool(self._get_store)
            if not await run_in_threadpool(store.reserve, key, lease_nonce, 90, self.rate_limit_minutes * 60):
                return {"success": False, "error": f"Повторная отправка возможна через {self.rate_limit_minutes} минут", "error_code": "RATE_LIMITED"}

            code = self.generate_verification_code()
            code_nonce = secrets.token_urlsafe(24)
            created = time.time()
            expires = created + self.code_ttl_minutes * 60
            expires_monotonic = time.monotonic() + self.code_ttl_minutes * 60
            templates = {
                "verification": "Ваш код подтверждения: {code}. Код действителен 5 минут.",
                "password_reset": "Код для сброса пароля: {code}. Код действителен 5 минут.",
                "phone_change": "Код для смены номера телефона: {code}. Код действителен 5 минут.",
                "registration": "Код для регистрации: {code}. Код действителен 5 минут.",
            }
            message = (custom_message or templates.get(purpose, "Ваш код: {code}")).replace("{code}", code)
            result = await asyncio.wait_for(
                self.sms_manager.send_sms(phone=phone, text=message, provider_type=provider_type),
                timeout=30,
            )
            if not allow_mock and str(result.provider or "").lower() == "mock":
                raise PhoneStoreUnavailable("SMS provider unavailable")
            if not result.success:
                logger.warning("Phone verification SMS delivery failed")
                return {"success": False, "error": "Ошибка отправки SMS", "error_code": "SMS_SEND_FAILED"}
            remaining = math.floor(expires_monotonic - time.monotonic())
            if remaining <= 0:
                raise PhoneStoreUnavailable("Verification send expired")
            record = {
                "version": 1, "nonce": code_nonce, "digest": self._code_digest(key, code_nonce, code),
                "owner": owner, "account_binding": account_binding, "purpose": purpose,
                "created_at": created, "expires_at": expires, "attempts": 0,
                "verified": False, "provider": result.provider,
            }
            published = await run_in_threadpool(
                store.publish, key, lease_nonce, json.dumps(record, separators=(",", ":")),
                remaining, self.rate_limit_minutes * 60, self.code_ttl_minutes * 60, 90,
            )
            if not published:
                raise PhoneStoreUnavailable("Verification send reservation expired")
            remaining = math.floor(expires_monotonic - time.monotonic())
            if remaining <= 0:
                raise PhoneStoreUnavailable("Verification send expired")
            logger.info("Phone verification SMS delivered")
            return {"success": True, "message": "Код верификации отправлен", "expires_in_minutes": math.ceil(remaining / 60), "expires_in_seconds": remaining, "message_id": result.message_id, "provider": result.provider}
        except PhoneStoreUnavailable as exc:
            logger.warning("Phone verification storage error: %s", type(exc).__name__)
            raise
        except Exception as exc:
            logger.warning("Phone verification send failed: %s", type(exc).__name__)
            return {"success": False, "error": "Ошибка отправки SMS", "error_code": "SMS_SEND_FAILED"}
        finally:
            if store is not None and not published:
                try:
                    await run_in_threadpool(store.release, key, lease_nonce)
                except Exception as exc:
                    logger.warning("Phone verification lease release failed: %s", type(exc).__name__)

    def verify_code(
        self, phone: str, code: str, purpose: str = "verification",
        remove_after_verification: bool = True, include_account_binding: bool = False,
        *, actor_id: int | None = None, actor_epoch: int | None = None,
        actor_jti: str | None = None, allow_admin: bool = False,
    ) -> dict[str, Any]:
        """Atomically authorize, count attempts and consume a one-time proof."""
        internal = include_account_binding and purpose == "password_reset"
        actor = _identity(actor_id, actor_epoch, actor_jti)
        if (purpose == "password_reset" and not internal) or (not internal and actor is None):
            return _missing()
        try:
            store = self._get_store()
            key = self._get_code_key(phone, purpose)
            record = store.status(key, actor, allow_admin, internal)
            if record is None or not isinstance(record.get("nonce"), str):
                return _missing()
            digest = self._code_digest(key, record["nonce"], code)
            consume_started = time.monotonic()
            outcome, record = store.verify(key, record["nonce"], digest, actor, allow_admin, internal, remove_after_verification, self.max_attempts)
            if outcome == "missing" or record is None:
                return _missing()
            if outcome == "locked":
                return {"success": False, "error": f"Превышено максимальное количество попыток ({self.max_attempts})", "error_code": "MAX_ATTEMPTS_EXCEEDED"}
            if outcome == "invalid":
                left = max(0, self.max_attempts - record["attempts"])
                return {"success": False, "error": f"Неверный код. Осталось попыток: {left}", "error_code": "INVALID_CODE", "attempts_left": left}
            binding = record.get("account_binding")
            if internal and (not isinstance(binding, list) or len(binding) != 2 or type(binding[0]) is not int or type(binding[1]) is not int):
                return _missing()
            expires_at = record.get("expires_at")
            if internal and (type(expires_at) not in (int, float) or not math.isfinite(expires_at) or expires_at <= 0):
                return _missing()
            ttl = record.get("_remaining_ttl_ms")
            if internal and (type(ttl) is not int or ttl <= 0):
                return _missing()
            result = {"success": True, "message": "Номер телефона успешно подтвержден", "phone": phone, "purpose": purpose, "verified_at": datetime.now(UTC).isoformat()}
            if internal:
                result["account_binding"] = tuple(binding)
                result["expires_at"] = expires_at
                result["expires_monotonic"] = consume_started + ttl / 1000
            return result
        except PhoneStoreUnavailable:
            raise
        except Exception as exc:
            logger.warning("Phone verification check failed: %s", type(exc).__name__)
            raise PhoneStoreUnavailable("Phone verification check unavailable") from exc

    def get_verification_status(
        self, phone: str, purpose: str = "verification", *, actor_id: int | None = None,
        actor_epoch: int | None = None, actor_jti: str | None = None, allow_admin: bool = False,
    ) -> dict[str, Any]:
        actor = _identity(actor_id, actor_epoch, actor_jti)
        if purpose == "password_reset" or actor is None:
            return {"exists": False, "verified": False}
        try:
            record = self._get_store().status(self._get_code_key(phone, purpose), actor, allow_admin)
            if record is None:
                return {"exists": False, "verified": False}
            return {"exists": True, "verified": bool(record.get("verified")), "phone": phone, "purpose": purpose,
                    "created_at": datetime.fromtimestamp(record["created_at"], UTC).isoformat(),
                    "expires_at": datetime.fromtimestamp(record["expires_at"], UTC).isoformat(),
                    "attempts": record["attempts"], "max_attempts": self.max_attempts,
                    "time_left_minutes": max(0, int((record["expires_at"] - time.time()) / 60))}
        except PhoneStoreUnavailable:
            raise
        except Exception as exc:
            logger.warning("Phone verification status failed: %s", type(exc).__name__)
            raise PhoneStoreUnavailable("Phone verification status unavailable") from exc

    def cancel_verification(
        self, phone: str, purpose: str = "verification", *, actor_id: int | None = None,
        actor_epoch: int | None = None, actor_jti: str | None = None, allow_admin: bool = False,
    ) -> bool:
        actor = _identity(actor_id, actor_epoch, actor_jti)
        if purpose == "password_reset" or actor is None:
            return False
        try:
            return self._get_store().cancel(self._get_code_key(phone, purpose), actor, allow_admin)
        except PhoneStoreUnavailable:
            raise
        except Exception as exc:
            logger.warning("Phone verification cancellation failed: %s", type(exc).__name__)
            raise PhoneStoreUnavailable("Phone verification cancellation unavailable") from exc

    def get_statistics(self) -> dict[str, Any]:
        try:
            records = self._get_store().statistics()
            verified = sum(record.get("verified") is True for record in records)
            purposes: dict[str, int] = {}
            providers: dict[str, int] = {}
            for record in records:
                purpose = record.get("purpose") or "unknown"
                provider = record.get("provider") or "unknown"
                purposes[purpose] = purposes.get(purpose, 0) + 1
                providers[provider] = providers.get(provider, 0) + 1
            return {"total_active_codes": len(records), "verified_codes": verified,
                    "pending_codes": len(records) - verified,
                    "expiring_soon": sum(record["expires_at"] - time.time() < 60 for record in records),
                    "by_purpose": purposes, "by_provider": providers,
                    "settings": {"code_length": self.code_length, "ttl_minutes": self.code_ttl_minutes,
                                 "max_attempts": self.max_attempts, "rate_limit_minutes": self.rate_limit_minutes}}
        except PhoneStoreUnavailable:
            raise
        except Exception as exc:
            logger.warning("Phone verification statistics failed: %s", type(exc).__name__)
            raise PhoneStoreUnavailable("Phone verification statistics unavailable") from exc


phone_verification_service = PhoneVerificationService()


def get_phone_verification_service() -> PhoneVerificationService:
    return phone_verification_service
