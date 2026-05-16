"""
API endpoints для управления Telegram в админ панели
"""

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, NoReturn, Optional

import requests
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import settings
from app.crud import clinic as crud_clinic, telegram_config as crud_telegram
from app.models.user import User
from app.services.telegram_bot import (
    PATIENT_BOT_COMMANDS_RU,
    PATIENT_BOT_COMMANDS_UZ,
    get_telegram_bot_service,
)

router = APIRouter()
logger = logging.getLogger(__name__)

STAFF_LINK_TOKEN_PREFIX = "stl"
STAFF_LINK_TOKEN_HASH_PREFIX = "staff_link_token:"
STAFF_LINK_TOKEN_SEPARATOR = "_"

STAFF_BOT_SUPPORTED_ROLES = [
    "registrar",
    "doctor",
    "cashier",
    "lab",
    "admin",
    "owner",
]

STAFF_BOT_READINESS = [
    {
        "key": "role_based_staff_linking",
        "label": "Ролевая привязка сотрудников",
        "ready": False,
    },
    {
        "key": "server_side_authorization",
        "label": "Проверка ролей на backend",
        "ready": False,
    },
    {
        "key": "audit_logging",
        "label": "Аудит действий сотрудников",
        "ready": False,
    },
    {
        "key": "state_change_confirmations",
        "label": "Подтверждения для операций",
        "ready": False,
    },
]

STAFF_BOT_READ_ONLY_MENU_CONTRACT = [
    {
        "role": "registrar",
        "label": "Регистратор",
        "items": [
            {"key": "queue_overview", "label": "Очередь", "intent": "read_only"},
            {"key": "next_patient", "label": "Следующий пациент", "intent": "read_only"},
            {"key": "payment_status", "label": "Статус оплаты", "intent": "read_only"},
        ],
    },
    {
        "role": "doctor",
        "label": "Врач",
        "items": [
            {"key": "today_schedule", "label": "Расписание на сегодня", "intent": "read_only"},
            {"key": "next_patient", "label": "Следующий пациент", "intent": "read_only"},
            {"key": "emr_reminders", "label": "Напоминания ЭМК", "intent": "read_only"},
        ],
    },
    {
        "role": "cashier",
        "label": "Кассир",
        "items": [
            {"key": "unpaid_invoices", "label": "Неоплаченные счета", "intent": "read_only"},
            {"key": "paid_invoices", "label": "Оплаченные счета", "intent": "read_only"},
            {"key": "reconciliation_alerts", "label": "Сверка оплат", "intent": "read_only"},
        ],
    },
    {
        "role": "lab",
        "label": "Лаборатория",
        "items": [
            {"key": "ready_reports", "label": "Готовые результаты", "intent": "read_only"},
            {"key": "pending_reports", "label": "Ожидающие результаты", "intent": "read_only"},
            {"key": "delivery_status", "label": "Статус доставки", "intent": "read_only"},
        ],
    },
    {
        "role": "admin",
        "label": "Администратор",
        "items": [
            {"key": "daily_summary", "label": "Дневная сводка", "intent": "read_only"},
            {"key": "integration_errors", "label": "Ошибки интеграций", "intent": "read_only"},
            {"key": "staff_readiness", "label": "Готовность staff bot", "intent": "read_only"},
        ],
    },
    {
        "role": "owner",
        "label": "Владелец",
        "items": [
            {"key": "daily_summary", "label": "Дневная сводка", "intent": "read_only"},
            {"key": "revenue_summary", "label": "Сводка выручки", "intent": "read_only"},
            {"key": "integration_errors", "label": "Ошибки интеграций", "intent": "read_only"},
        ],
    },
]

STAFF_BOT_GUARDRAILS = [
    "server_side_authorization",
    "audit_logging",
    "explicit_confirmation_for_state_changes",
    "no_queue_fairness_mutation_without_domain_service",
]

STAFF_BOT_TOKEN_CONTRACT = {
    "contract_version": "staff-token-v1",
    "enabled": False,
    "runtime_read_enabled": False,
    "required_before_enablement": True,
    "scope": "dedicated_staff_bot",
    "must_not_share_patient_bot_token": True,
    "secret_source": "environment_or_secret_store",
    "required_server_checks": [
        "separate_staff_bot_token_configured",
        "token_not_logged",
        "token_not_returned_to_frontend",
        "staff_webhook_or_polling_transport_selected",
        "patient_bot_transport_unchanged",
    ],
    "enablement_gate": [
        "dedicated_staff_bot_token",
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
}

STAFF_BOT_LINKING_CONTRACT = {
    "contract_version": "staff-linking-v1",
    "enabled": False,
    "required_before_enablement": True,
    "identity_rule": "telegram_user_id_is_not_application_identity",
    "accepted_methods": [
        {
            "key": "admin_verified_staff_link",
            "label": "Администратор подтверждает сотрудника",
            "status": "planned",
        },
        {
            "key": "one_time_signed_staff_token",
            "label": "Одноразовый подписанный токен",
            "status": "planned",
        },
    ],
    "required_server_checks": [
        "active_application_user",
        "allowed_staff_role",
        "telegram_user_not_linked_to_another_staff_user",
        "token_not_expired",
        "token_not_reused",
    ],
    "enablement_gate": [
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
    "state_changing_actions_allowed_after_link": False,
}

STAFF_BOT_LINKING_RUNTIME_CONTRACT = {
    "contract_version": "staff-linking-runtime-v1",
    "enabled": False,
    "helper_available": True,
    "runtime_handler_enabled": False,
    "write_helper": "link_staff_user_to_telegram",
    "lookup_helpers": [
        "get_telegram_user_by_chat_id",
        "get_telegram_user_by_linked_user_id",
    ],
    "writes": [
        "telegram_users.user_id",
    ],
    "requires_prevalidated_inputs": [
        "active_application_user",
        "allowed_staff_role",
        "one_time_link_token_validated",
        "telegram_user_not_linked_to_another_staff_user",
    ],
    "state_changing_actions_allowed_after_link": False,
}

STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT = {
    "contract_version": "staff-link-token-storage-v1",
    "enabled": False,
    "migration_created": False,
    "runtime_write_enabled": False,
    "table": "telegram_staff_link_tokens",
    "raw_token_storage_allowed": False,
    "columns": [
        "id",
        "token_hash",
        "staff_user_id",
        "telegram_chat_id",
        "expires_at",
        "consumed_at",
        "issued_by_user_id",
        "created_at",
        "request_id",
    ],
    "required_indexes": [
        "unique(token_hash)",
        "index(staff_user_id)",
        "index(telegram_chat_id)",
        "partial_index(expires_at) where consumed_at is null",
    ],
    "required_constraints": [
        "expires_at > created_at",
        "consumed_at is null or consumed_at <= expires_at",
        "staff_user_id references users(id)",
    ],
    "retention_policy": {
        "expired_token_ttl_days": 7,
        "consumed_token_ttl_days": 30,
    },
}

STAFF_BOT_LINK_TOKEN_VALIDATION_CONTRACT = {
    "contract_version": "staff-link-token-validation-v1",
    "enabled": False,
    "validator_enabled": True,
    "runtime_helper_available": True,
    "signature_validator_available": True,
    "expiry_validator_available": True,
    "binding_parser_available": True,
    "stateless_validator_enabled": True,
    "single_use_enforcement_enabled": False,
    "token_storage_enabled": False,
    "handler_enabled": False,
    "storage_migration_required": True,
    "storage_contract": STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT,
    "runtime_blocked_by": [
        "staff_link_token_storage_migration",
        "staff_link_token_validator_service",
    ],
    "required_before_enablement": True,
    "token_format": "stl_<user_id>_<chat_id>_<expires_at>_<nonce>_<signature>",
    "builder": "build_staff_link_start_token",
    "parser": "parse_staff_link_start_token",
    "validator": "validate_staff_link_start_token",
    "token_hash_prefix": STAFF_LINK_TOKEN_HASH_PREFIX,
    "token_properties": [
        "signed",
        "single_use",
        "expires_at",
        "bound_to_application_user_id",
        "bound_to_telegram_chat_id",
    ],
    "rejection_reasons": [
        "expired",
        "signature_invalid",
        "already_used",
        "staff_user_inactive",
        "role_not_allowed",
        "telegram_account_already_linked",
        "staff_user_already_linked",
    ],
    "required_audit_events": [
        "staff_link_token_issued",
        "staff_link_token_consumed",
        "staff_link_token_rejected",
    ],
}

STAFF_BOT_AUTHORIZATION_CONTRACT = {
    "contract_version": "staff-authorization-v1",
    "enabled": False,
    "source": "application_rbac",
    "server_side_required": True,
    "default_decision": "deny",
    "role_checks": [
        {
            "role": "registrar",
            "allowed_intents": ["queue_read", "patient_lookup_read", "payment_status_read"],
        },
        {
            "role": "doctor",
            "allowed_intents": ["schedule_read", "next_patient_read", "emr_reminder_read"],
        },
        {
            "role": "cashier",
            "allowed_intents": ["invoice_read", "payment_reconciliation_read"],
        },
        {
            "role": "lab",
            "allowed_intents": ["report_status_read", "result_delivery_status_read"],
        },
        {
            "role": "admin",
            "allowed_intents": ["operations_summary_read", "integration_error_read"],
        },
        {
            "role": "owner",
            "allowed_intents": ["operations_summary_read", "revenue_summary_read"],
        },
    ],
    "denied_behavior": [
        "send_generic_forbidden_message",
        "do_not_execute_domain_action",
        "write_audit_denied_event_when_audit_enabled",
    ],
}

STAFF_BOT_COMMAND_REGISTRATION_CONTRACT = {
    "contract_version": "staff-commands-v1",
    "registration_enabled": False,
    "registration_endpoint_published": False,
    "bot_scope": "staff_bot_only",
    "commands": [
        {
            "command": "/staff",
            "label": "Статус сотрудника",
            "intent": "read_only",
        },
        {
            "command": "/queue",
            "label": "Очередь по роли",
            "intent": "read_only",
        },
        {
            "command": "/schedule",
            "label": "Расписание",
            "intent": "read_only",
        },
        {
            "command": "/payments",
            "label": "Статусы оплат",
            "intent": "read_only",
        },
        {
            "command": "/reports",
            "label": "Готовность результатов",
            "intent": "read_only",
        },
        {
            "command": "/summary",
            "label": "Операционная сводка",
            "intent": "read_only",
        },
        {
            "command": "/help",
            "label": "Помощь сотруднику",
            "intent": "read_only",
        },
    ],
    "enablement_gate": [
        "dedicated_staff_bot_token",
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
    "state_changing_commands_registered": False,
}

STAFF_BOT_CONFIRMATION_CONTRACT = {
    "contract_version": "staff-confirmations-v1",
    "enabled": False,
    "required_for_state_changes": True,
    "state_changing_actions_enabled": False,
    "confirmation_window_seconds": 120,
    "operations": [
        {
            "key": "queue_call_or_skip_patient",
            "label": "Вызвать или пропустить пациента",
            "roles": ["registrar"],
            "domain_service_required": "queue",
        },
        {
            "key": "visit_cancel_or_move",
            "label": "Отменить или перенести визит",
            "roles": ["registrar", "admin"],
            "domain_service_required": "visit",
        },
        {
            "key": "payment_status_change",
            "label": "Изменить статус оплаты",
            "roles": ["cashier", "admin"],
            "domain_service_required": "payment",
        },
        {
            "key": "refund_issue",
            "label": "Оформить возврат",
            "roles": ["cashier", "admin", "owner"],
            "domain_service_required": "payment",
        },
        {
            "key": "medical_document_publish",
            "label": "Закрыть ЭМК или опубликовать документ",
            "roles": ["doctor", "lab", "admin"],
            "domain_service_required": "emr_or_lab",
        },
        {
            "key": "doctor_schedule_change",
            "label": "Изменить расписание врача",
            "roles": ["admin", "owner"],
            "domain_service_required": "schedule",
        },
    ],
    "required_server_checks": [
        "staff_linked_to_active_application_user",
        "role_allowed_for_operation",
        "fresh_confirmation_token",
        "idempotency_key_present",
        "domain_service_authorizes_target",
        "audit_log_write_succeeds",
    ],
    "telegram_payload_rules": [
        "no_raw_internal_ids",
        "no_plain_medical_details",
        "short_human_readable_summary_only",
    ],
}

STAFF_BOT_AUDIT_CONTRACT = {
    "contract_version": "staff-audit-v1",
    "enabled": False,
    "record_writer_enabled": False,
    "required_before_enablement": True,
    "event_types": [
        {
            "key": "staff_link_created",
            "label": "Привязка сотрудника к Telegram",
            "required": True,
        },
        {
            "key": "staff_command_received",
            "label": "Команда сотрудника получена",
            "required": True,
        },
        {
            "key": "staff_action_confirmation_requested",
            "label": "Запрошено подтверждение действия",
            "required": True,
        },
        {
            "key": "staff_action_confirmed",
            "label": "Действие подтверждено сотрудником",
            "required": True,
        },
        {
            "key": "staff_action_denied",
            "label": "Действие запрещено серверной проверкой",
            "required": True,
        },
        {
            "key": "staff_action_failed",
            "label": "Действие завершилось ошибкой",
            "required": True,
        },
    ],
    "required_fields": [
        "actor_user_id",
        "actor_role",
        "telegram_user_id_hash",
        "action_key",
        "target_type",
        "target_reference_hash",
        "result",
        "timestamp",
        "request_id",
    ],
    "redaction_rules": [
        "no_bot_tokens",
        "no_raw_telegram_payload",
        "no_plain_medical_details",
        "no_raw_internal_identifiers_in_chat_text",
    ],
}

STAFF_BOT_ROLE_MENU_ENABLEMENT_CONTRACT = {
    "contract_version": "staff-role-menu-enablement-v1",
    "enabled": False,
    "runtime_menu_enabled": False,
    "read_only_contract_published": True,
    "required_before_enablement": True,
    "state_changing_menu_items_enabled": False,
    "allowed_until_enabled": [
        "read_status_contract",
        "read_only_menu_preview",
    ],
    "required_server_checks": [
        "dedicated_staff_bot_token",
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
}


def _base36_encode(value: int) -> str:
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _base36_decode(value: str) -> int:
    return int(value, 36)


def _staff_link_token_expires_epoch(expires_at: datetime) -> int:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = expires_at.astimezone(timezone.utc)
    return int(expires_at.timestamp())


def _staff_link_token_signature(body: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base36_encode(int.from_bytes(digest[:12], "big"))


def _hash_staff_link_start_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{STAFF_LINK_TOKEN_HASH_PREFIX}{digest}"


def build_staff_link_start_token(
    *,
    user_id: int,
    chat_id: int,
    expires_at: datetime,
    nonce: str | None = None,
) -> str:
    if user_id <= 0 or chat_id == 0:
        raise ValueError(
            "staff link token requires positive user_id and nonzero chat_id"
        )
    token_nonce = nonce or _base36_encode(secrets.randbits(64))
    body = STAFF_LINK_TOKEN_SEPARATOR.join(
        [
            STAFF_LINK_TOKEN_PREFIX,
            str(user_id),
            str(chat_id),
            _base36_encode(_staff_link_token_expires_epoch(expires_at)),
            token_nonce,
        ]
    )
    signature = _staff_link_token_signature(body)
    return f"{body}{STAFF_LINK_TOKEN_SEPARATOR}{signature}"


def _decode_staff_link_start_token(
    token: str,
) -> tuple[Dict[str, Any] | None, str | None]:
    parts = (token or "").split(STAFF_LINK_TOKEN_SEPARATOR)
    if len(parts) != 6 or parts[0] != STAFF_LINK_TOKEN_PREFIX:
        return None, "signature_invalid"

    body = STAFF_LINK_TOKEN_SEPARATOR.join(parts[:5])
    if not hmac.compare_digest(parts[5], _staff_link_token_signature(body)):
        return None, "signature_invalid"

    try:
        user_id = int(parts[1])
        chat_id = int(parts[2])
        expires_at = datetime.fromtimestamp(
            _base36_decode(parts[3]),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None, "signature_invalid"

    if user_id <= 0 or chat_id == 0:
        return None, "signature_invalid"

    decoded = {
        "user_id": user_id,
        "chat_id": chat_id,
        "expires_at": expires_at.replace(tzinfo=None),
        "token_hash": _hash_staff_link_start_token(token),
    }
    if expires_at < datetime.now(timezone.utc):
        return decoded, "expired"
    return decoded, None


def parse_staff_link_start_token(token: str) -> Dict[str, Any] | None:
    decoded, rejection_reason = _decode_staff_link_start_token(token)
    if rejection_reason:
        return None
    return decoded


def _normalize_staff_role(role: Any) -> str:
    role_key = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    role_aliases = {
        "administrator": "admin",
        "admin": "admin",
        "owner": "owner",
        "doctor": "doctor",
        "cashier": "cashier",
        "lab": "lab",
        "lab_tech": "lab",
        "laboratory": "lab",
        "registrar": "registrar",
        "receptionist": "registrar",
    }
    return role_aliases.get(role_key, role_key)


def validate_staff_link_start_token(
    db: Session, token: str, telegram_chat_id: int
) -> Dict[str, Any]:
    parsed, rejection_reason = _decode_staff_link_start_token(token)
    if not parsed:
        return {"valid": False, "reason": rejection_reason or "signature_invalid"}

    if rejection_reason == "expired":
        return {
            "valid": False,
            "reason": "expired",
            "token_hash": parsed["token_hash"],
        }

    if int(parsed["chat_id"]) != int(telegram_chat_id):
        return {
            "valid": False,
            "reason": "chat_mismatch",
            "token_hash": parsed["token_hash"],
        }

    user = db.query(User).filter(User.id == parsed["user_id"]).first()
    if not user or not user.is_active:
        return {
            "valid": False,
            "reason": "staff_user_inactive",
            "token_hash": parsed["token_hash"],
        }

    role_key = _normalize_staff_role(user.role)
    if role_key not in STAFF_BOT_SUPPORTED_ROLES:
        return {
            "valid": False,
            "reason": "role_not_allowed",
            "role": role_key,
            "token_hash": parsed["token_hash"],
        }

    telegram_user = crud_telegram.get_telegram_user_by_chat_id(
        db, int(parsed["chat_id"])
    )
    linked_user_id = getattr(telegram_user, "user_id", None)
    if linked_user_id and int(linked_user_id) != int(user.id):
        return {
            "valid": False,
            "reason": "telegram_account_already_linked",
            "token_hash": parsed["token_hash"],
        }

    linked_telegram_user = crud_telegram.get_telegram_user_by_linked_user_id(
        db, int(user.id)
    )
    linked_chat_id = getattr(linked_telegram_user, "chat_id", None)
    if linked_chat_id and int(linked_chat_id) != int(parsed["chat_id"]):
        return {
            "valid": False,
            "reason": "staff_user_already_linked",
            "token_hash": parsed["token_hash"],
        }

    logger.info("Staff Telegram link token validated role=%s", role_key)
    return {
        "valid": True,
        "reason": "ok",
        "token_hash": parsed["token_hash"],
        "user_id": int(user.id),
        "chat_id": int(parsed["chat_id"]),
        "role": role_key,
        "expires_at": parsed["expires_at"].isoformat(),
        "single_use_enforced": False,
    }


def _build_staff_role_menus_summary() -> Dict[str, Any]:
    menu_roles = [
        role_menu["role"] for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT
    ]
    menu_item_count = sum(
        len(role_menu.get("items", []))
        for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT
    )
    return {
        "contract_published": True,
        "runtime_enabled": False,
        "read_only": True,
        "source": "read_only_menu_contract",
        "roles": menu_roles,
        "role_count": len(menu_roles),
        "item_count": menu_item_count,
        "blocked_until": [
            "role_based_staff_linking",
            "server_side_authorization",
            "audit_logging",
            "state_change_confirmations",
        ],
    }


def _build_staff_role_menu_enablement_contract(
    role_menus: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        **STAFF_BOT_ROLE_MENU_ENABLEMENT_CONTRACT,
        "roles_covered": role_menus["roles"],
        "role_count": role_menus["role_count"],
        "menu_item_count": role_menus["item_count"],
    }


def _build_staff_bot_status(webhook_set: bool) -> Dict[str, Any]:
    role_menus = _build_staff_role_menus_summary()
    return {
        "version": "planning",
        "contract_version": "staff-menu-read-only-v1",
        "enabled": False,
        "contract_published": True,
        "status": "requires_role_linking_audit_and_confirmations",
        "transport": "polling" if not webhook_set else "webhook",
        "supported_languages": [
            {"code": "ru", "label": "Русский"},
        ],
        "supported_roles": STAFF_BOT_SUPPORTED_ROLES,
        "role_linking": {
            "enabled": False,
            "required_before_enablement": True,
            "accepted_methods": [
                "admin_verified_staff_link",
                "one_time_signed_staff_token",
            ],
        },
        "token_contract": STAFF_BOT_TOKEN_CONTRACT,
        "linking_contract": STAFF_BOT_LINKING_CONTRACT,
        "linking_runtime_contract": STAFF_BOT_LINKING_RUNTIME_CONTRACT,
        "link_token_validation_contract": STAFF_BOT_LINK_TOKEN_VALIDATION_CONTRACT,
        "link_token_storage_contract": STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT,
        "authorization_contract": STAFF_BOT_AUTHORIZATION_CONTRACT,
        "command_registration_contract": STAFF_BOT_COMMAND_REGISTRATION_CONTRACT,
        "confirmation_contract": STAFF_BOT_CONFIRMATION_CONTRACT,
        "audit_contract": STAFF_BOT_AUDIT_CONTRACT,
        "authorization": {
            "source": "application_rbac",
            "server_side_required": True,
            "ready": False,
        },
        "audit": {
            "required": True,
            "ready": False,
        },
        "state_changing_actions_enabled": False,
        "readiness": STAFF_BOT_READINESS,
        "role_menus": role_menus,
        "role_menu_enablement_contract": (
            _build_staff_role_menu_enablement_contract(role_menus)
        ),
        "read_only_menu_contract": STAFF_BOT_READ_ONLY_MENU_CONTRACT,
        "guardrails": STAFF_BOT_GUARDRAILS,
        "next_slice": "staff_link_token_storage_migration",
    }


def raise_admin_telegram_error(
    action: str,
    public_detail: str,
    exc: Exception,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> NoReturn:
    logger.warning(
        "Admin Telegram endpoint failed action=%s status_code=%s error_type=%s",
        action,
        status_code,
        type(exc).__name__,
    )
    raise HTTPException(status_code=status_code, detail=public_detail)


def webhook_info_error_response(
    action: str, public_error: str, exc: Exception
) -> Dict[str, Any]:
    logger.warning(
        "Admin Telegram webhook info failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    return {"webhook_set": False, "error": public_error}


class TelegramWebhookRequest(BaseModel):
    webhook_url: Optional[str] = None


def _get_configured_bot_token(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_token:
        return config.bot_token

    bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
    return getattr(bot_token_setting, "value", None) if bot_token_setting else None


def _get_configured_bot_username(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_username:
        return config.bot_username

    bot_username_setting = crud_clinic.get_setting_by_key(db, "bot_username")
    return (
        getattr(bot_username_setting, "value", None) if bot_username_setting else None
    )


def _fetch_telegram_webhook_info(bot_token: str) -> Dict[str, Any]:
    response = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or "Telegram API error")
    return result["result"]

# ===================== НАСТРОЙКИ TELEGRAM =====================


@router.get("/telegram/settings")
def get_telegram_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки Telegram"""
    try:
        telegram_settings = crud_clinic.get_settings_by_category(db, "telegram")

        result = {
            "bot_token": "",
            "webhook_url": "",
            "admin_chat_ids": [],
            "notifications_enabled": True,
            "appointment_reminders": True,
            "lab_results_notifications": True,
            "payment_notifications": True,
            "default_language": "ru",
            "supported_languages": ["ru", "uz-Latn"],
        }

        # Применяем сохраненные настройки
        for setting in telegram_settings:
            if setting.key in result:
                result[setting.key] = setting.value

        # Скрываем токен бота в ответе
        if result["bot_token"]:
            result["bot_token_masked"] = "***скрыт***"
            result["bot_token_length"] = len(result["bot_token"])
            result["bot_token"] = "***скрыт***"

        return result
    except Exception as e:
        raise_admin_telegram_error(
            "settings-read",
            "Ошибка получения настроек Telegram",
            e,
        )


@router.put("/telegram/settings")
def update_telegram_settings(
    settings: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки Telegram"""
    try:
        # Обновляем настройки в категории "telegram"
        updated_settings = crud_clinic.update_settings_batch(
            db, "telegram", settings, current_user.id
        )

        return {
            "success": True,
            "message": "Настройки Telegram обновлены",
            "updated_count": len(updated_settings),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "settings-update",
            "Ошибка обновления настроек Telegram",
            e,
        )


@router.post("/telegram/test-bot")
def test_telegram_bot(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать подключение к Telegram боту"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Тестируем подключение к API Telegram
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get("ok"):
                bot_data = bot_info["result"]

                # Сохраняем информацию о боте
                crud_clinic.update_settings_batch(
                    db,
                    "telegram",
                    {
                        "bot_username": bot_data.get("username"),
                        "bot_name": bot_data.get("first_name"),
                    },
                    current_user.id,
                )
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": bot_data.get("username"),
                    "bot_name": bot_data.get("first_name"),
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

                return {
                    "success": True,
                    "message": "Подключение к боту успешно",
                    "bot_info": {
                        "id": bot_data.get("id"),
                        "username": bot_data.get("username"),
                        "first_name": bot_data.get("first_name"),
                        "can_join_groups": bot_data.get("can_join_groups"),
                        "can_read_all_group_messages": bot_data.get(
                            "can_read_all_group_messages"
                        ),
                    },
                }
            else:
                raise Exception(f"Ошибка API Telegram: {bot_info.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "test-bot-request",
            "Ошибка подключения к Telegram API",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "test-bot",
            "Ошибка тестирования бота",
            e,
        )


@router.post("/telegram/register-patient-commands")
async def register_patient_bot_commands(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Register patient bot commands in Telegram via the configured bot token."""
    try:
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot token is not configured",
            )

        bot_service = await get_telegram_bot_service()
        bot_service.bot_token = bot_token
        ok, error = await bot_service.set_patient_bot_commands()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Telegram patient bot commands were not registered",
                    "error": error,
                },
            )

        return {
            "success": True,
            "message": "Telegram patient bot commands registered",
            "registered_languages": ["ru", "uz"],
            "commands": {
                "ru": PATIENT_BOT_COMMANDS_RU,
                "uz": PATIENT_BOT_COMMANDS_UZ,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "register-patient-commands",
            "Telegram patient bot command registration failed",
            e,
        )


@router.post("/telegram/set-webhook")
def set_telegram_webhook(
    payload: Optional[TelegramWebhookRequest] = Body(default=None),
    webhook_url: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установить webhook для Telegram бота"""
    try:
        selected_webhook_url = (payload.webhook_url if payload else None) or webhook_url
        if not selected_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="webhook_url is required",
            )

        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        secret_token = secrets.token_urlsafe(32)

        # Устанавливаем webhook
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": selected_webhook_url, "secret_token": secret_token},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                # Сохраняем URL webhook
                crud_clinic.update_setting(
                    db, "webhook_url", {"value": selected_webhook_url}, current_user.id
                )
                config_payload = {
                    "bot_token": bot_token,
                    "bot_username": _get_configured_bot_username(db),
                    "webhook_url": selected_webhook_url,
                    "webhook_secret": secret_token,
                    "active": True,
                }
                if crud_telegram.get_telegram_config(db):
                    crud_telegram.update_telegram_config(db, config_payload)
                else:
                    crud_telegram.create_telegram_config(db, config_payload)

                return {
                    "success": True,
                    "message": "Webhook установлен успешно",
                    "webhook_url": selected_webhook_url,
                    "webhook_secret_configured": True,
                }
            else:
                raise Exception(
                    f"Ошибка установки webhook: {result.get('description')}"
                )
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "set-webhook-request",
            "Ошибка установки webhook",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "set-webhook",
            "Ошибка установки webhook",
            e,
        )


@router.get("/telegram/webhook-info")
def get_telegram_webhook_info(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить информацию о webhook"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            return {"webhook_set": False, "message": "Токен бота не настроен"}

        # Получаем информацию о webhook
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result["result"]
                return {
                    "webhook_set": bool(webhook_info.get("url")),
                    "webhook_info": webhook_info,
                }
            else:
                raise Exception(f"Ошибка API: {result.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}")

    except requests.RequestException as e:
        return webhook_info_error_response(
            "webhook-info-request",
            "Ошибка подключения",
            e,
        )
    except Exception as e:
        return webhook_info_error_response(
            "webhook-info",
            "Ошибка получения информации о webhook",
            e,
        )


# ===================== ШАБЛОНЫ СООБЩЕНИЙ =====================


@router.get("/telegram/integration-status")
def get_telegram_integration_status(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Return app-facing Telegram integration status without exposing secrets."""
    try:
        config = crud_telegram.get_telegram_config(db)
        bot_token = _get_configured_bot_token(db)
        bot_username = _get_configured_bot_username(db)
        telegram_users = crud_telegram.get_telegram_users(
            db, active_only=False, limit=100000
        )
        linked_users = [user for user in telegram_users if user.patient_id]

        webhook_info = None
        webhook_error = None
        if bot_token:
            try:
                webhook_info = _fetch_telegram_webhook_info(bot_token)
            except requests.RequestException as exc:
                webhook_error = "Telegram API unavailable"
                logger.warning(
                    "Admin Telegram integration status request failed error_type=%s",
                    type(exc).__name__,
                )
            except Exception as exc:
                webhook_error = "Telegram webhook status unavailable"
                logger.warning(
                    "Admin Telegram integration status failed error_type=%s",
                    type(exc).__name__,
                )

        webhook_set = bool(webhook_info and webhook_info.get("url"))
        webhook_url = (
            webhook_info.get("url")
            if webhook_info
            else getattr(config, "webhook_url", None)
        )

        return {
            "configured": bool(bot_token),
            "active": bool(getattr(config, "active", False) or bot_token),
            "bot_username": bot_username,
            "mode": "webhook" if webhook_set else "polling",
            "polling_ready": bool(bot_token and not webhook_set),
            "polling_command": "python -m app.scripts.telegram_polling_worker",
            "polling_task_name": "KosmedTelegramPollingWorker",
            "webhook_set": webhook_set,
            "webhook_url": webhook_url,
            "webhook_error": webhook_error,
            "pending_update_count": (
                webhook_info.get("pending_update_count") if webhook_info else None
            ),
            "qr_linking_enabled": bool(bot_username),
            "contact_linking_enabled": bool(bot_token),
            "linked_users": len(linked_users),
            "total_users": len(telegram_users),
            "supported_functions": [
                "ticket_qr_link",
                "contact_phone_link",
                "patient_queue",
                "patient_payments_debt",
                "patient_status",
                "patient_language_notification_settings",
                "lab_results_pdf",
            ],
            "planned_functions": [
                "dedicated_staff_bot_token_readiness_contract",
                "staff_read_only_menu_contract",
                "staff_role_menu_enablement_status",
                "staff_role_linking_contract",
                "staff_role_linking_runtime",
                "staff_link_token_validation_contract",
                "staff_link_token_validation_runtime_helper",
                "staff_link_token_storage_migration_contract",
                "staff_server_side_authorization_contract",
                "staff_command_registration_contract",
                "staff_state_change_confirmation_contract",
                "staff_audit_logging_contract",
                "staff_role_menus",
                "staff_action_confirmations",
                "staff_audit_logging",
                "admin_notifications",
            ],
            "patient_bot": {
                "version": "v1",
                "transport": "polling" if not webhook_set else "webhook",
                "supported_languages": [
                    {"code": "ru", "label": "Русский"},
                    {"code": "uz-Latn", "label": "O'zbekcha"},
                ],
                "default_language": "ru",
                "onboarding": "language_choice_then_contact_link",
                "commands": [
                    {"command": "/queue", "label": "Моя очередь"},
                    {"command": "/payments", "label": "Оплаты и долг"},
                    {"command": "/results", "label": "PDF-результаты"},
                    {"command": "/profile", "label": "Мой статус"},
                    {"command": "/settings", "label": "Язык и уведомления"},
                    {"command": "/help", "label": "Помощь"},
                ],
                "features": [
                    {
                        "key": "ticket_qr_link",
                        "label": "Привязка через QR чека",
                        "enabled": bool(bot_username),
                    },
                    {
                        "key": "contact_phone_link",
                        "label": "Привязка через номер телефона",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_queue",
                        "label": "Очередь пациента на сегодня",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_payments_debt",
                        "label": "Оплаты и долг по визиту",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "lab_results_pdf",
                        "label": "PDF-результаты лаборатории",
                        "enabled": bool(bot_token),
                    },
                    {
                        "key": "patient_language_notification_settings",
                        "label": "Настройки языка и уведомлений",
                        "enabled": bool(bot_token),
                    },
                ],
                "results_delivery": "telegram_pdf",
                "max_pdf_reports_per_request": 3,
            },
            "staff_bot": _build_staff_bot_status(webhook_set),
            "transition_path": (
                "Set webhook when a public HTTPS backend URL is available; "
                "stop polling before webhook is enabled."
            ),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "integration-status",
            "Ошибка получения статуса Telegram интеграции",
            e,
        )


@router.get("/telegram/templates")
def get_telegram_templates(
    language: str = "ru",
    template_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить шаблоны сообщений"""
    try:
        # Здесь будет логика получения шаблонов из БД
        # Пока возвращаем базовые шаблоны

        base_templates = {
            "appointment_reminder": {
                "ru": {
                    "subject": "Напоминание о приеме",
                    "message_text": "Здравствуйте, {{patient_name}}!\n\nНапоминаем о приеме {{appointment_date}} в {{appointment_time}} у врача {{doctor_name}} ({{specialty}}).\n\nАдрес: {{clinic_address}}\nКабинет: {{cabinet}}\n\nПодтвердите или выберите действие:",
                    "buttons": [
                        {
                            "text": "✅ Подтвердить",
                            "callback_data": "confirm_{{appointment_id}}",
                        },
                        {
                            "text": "🔁 Перенести",
                            "callback_data": "reschedule_{{appointment_id}}",
                        },
                        {
                            "text": "❌ Отменить",
                            "callback_data": "cancel_{{appointment_id}}",
                        },
                    ],
                },
                "uz": {
                    "subject": "Qabul haqida eslatma",
                    "message_text": "Assalomu alaykum, {{patient_name}}!\n\n{{appointment_date}} kuni soat {{appointment_time}}da {{doctor_name}} shifokorining qabuliga eslatma ({{specialty}}).\n\nManzil: {{clinic_address}}\nXona: {{cabinet}}\n\nTasdiqlang yoki amalni tanlang:",
                    "buttons": [
                        {
                            "text": "✅ Tasdiqlash",
                            "callback_data": "confirm_{{appointment_id}}",
                        },
                        {
                            "text": "🔁 Ko'chirish",
                            "callback_data": "reschedule_{{appointment_id}}",
                        },
                        {
                            "text": "❌ Bekor qilish",
                            "callback_data": "cancel_{{appointment_id}}",
                        },
                    ],
                },
            },
            "lab_results_ready": {
                "ru": {
                    "subject": "Результаты анализов готовы",
                    "message_text": "Здравствуйте, {{patient_name}}!\n\nГотовы результаты анализов:\n{{lab_tests}}\n\nВы можете получить их в клинике или скачать по ссылке ниже.",
                    "buttons": [
                        {"text": "📄 Скачать результаты", "url": "{{download_link}}"}
                    ],
                },
                "uz": {
                    "subject": "Tahlil natijalari tayyor",
                    "message_text": "Assalomu alaykum, {{patient_name}}!\n\nTahlil natijalari tayyor:\n{{lab_tests}}\n\nUlarni klinikadan olishingiz yoki quyidagi havoladan yuklab olishingiz mumkin.",
                    "buttons": [
                        {
                            "text": "📄 Natijalarni yuklab olish",
                            "url": "{{download_link}}",
                        }
                    ],
                },
            },
            "payment_confirmation": {
                "ru": {
                    "subject": "Платеж подтвержден",
                    "message_text": "Платеж на сумму {{amount}} {{currency}} успешно обработан.\n\nСпасибо за оплату!\n\nЧек можете скачать по ссылке ниже.",
                    "buttons": [{"text": "🧾 Скачать чек", "url": "{{receipt_link}}"}],
                }
            },
        }

        if template_type:
            return base_templates.get(template_type, {}).get(language, {})

        # Возвращаем все шаблоны для языка
        result = {}
        for template_key, template_data in base_templates.items():
            if language in template_data:
                result[template_key] = template_data[language]

        return result

    except Exception as e:
        raise_admin_telegram_error(
            "templates",
            "Ошибка получения шаблонов",
            e,
        )


@router.post("/telegram/send-test-message")
def send_test_message(
    chat_id: int,
    message: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить тестовое сообщение"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Отправляем сообщение
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"🧪 Тестовое сообщение от Programma Clinic\n\n{message}\n\n⚙️ Отправлено из админ панели",
                "parse_mode": "HTML",
            },
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return {
                    "success": True,
                    "message": "Тестовое сообщение отправлено",
                    "message_id": result["result"]["message_id"],
                }
            else:
                raise Exception(f"Ошибка отправки: {result.get('description')}")
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    except requests.RequestException as e:
        raise_admin_telegram_error(
            "send-test-message-request",
            "Ошибка отправки сообщения",
            e,
            status.HTTP_400_BAD_REQUEST,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "send-test-message",
            "Ошибка отправки тестового сообщения",
            e,
        )


# ===================== СТАТИСТИКА TELEGRAM =====================


@router.get("/telegram/stats")
def get_telegram_stats(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin", "admin"])),
):
    """Получить статистику Telegram"""
    try:
        # Пока возвращаем заглушку, в будущем будет реальная статистика
        return {
            "total_users": 0,
            "active_users": 0,
            "messages_sent": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "by_message_type": {},
            "period_start": datetime.utcnow() - timedelta(days=days_back),
            "period_end": datetime.utcnow(),
        }
    except Exception as e:
        raise_admin_telegram_error(
            "stats",
            "Ошибка получения статистики Telegram",
            e,
        )


# ===================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====================


@router.get("/telegram/users")
def get_telegram_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin", "admin"])),
):
    """Получить список пользователей Telegram"""
    try:
        # Пока возвращаем заглушку
        return []
    except Exception as e:
        raise_admin_telegram_error(
            "users",
            "Ошибка получения пользователей Telegram",
            e,
        )


# ===================== ШИРОКОВЕЩАТЕЛЬНЫЕ СООБЩЕНИЯ =====================


@router.post("/telegram/broadcast")
def send_broadcast_message(
    message: str,
    target_groups: List[str],  # ["patients", "doctors", "admins"]
    language: str = "ru",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить широковещательное сообщение"""
    try:
        # Получаем токен бота
        bot_token = _get_configured_bot_token(db)
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Токен бота не настроен"
            )

        # Здесь будет логика отправки широковещательных сообщений
        # Пока возвращаем заглушку

        return {
            "success": True,
            "message": "Широковещательное сообщение поставлено в очередь",
            "target_groups": target_groups,
            "estimated_recipients": 0,  # Будет подсчитано из БД
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_admin_telegram_error(
            "broadcast",
            "Ошибка отправки сообщения",
            e,
        )
