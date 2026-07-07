"""Admin Telegram helpers, constants, and utility functions.

Split from admin_telegram.py (3343 LOC → modular).
"""
from __future__ import annotations

"""
API endpoints для управления Telegram в админ панели
"""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from html import escape
from typing import Any, NoReturn

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import settings
from app.crud import audit as crud_audit
from app.crud import clinic as crud_clinic
from app.crud import telegram_config as crud_telegram
from app.models.telegram_config import TelegramStaffConfirmationToken
from app.models.user import User
from app.services.telegram_bot import (
    PATIENT_BOT_COMMANDS_RU,
    PATIENT_BOT_COMMANDS_UZ,
    PATIENT_BOT_MENU_BUTTON,
    PATIENT_BOT_PROFILE_TEXTS,
    get_telegram_bot_service,
)
from app.services.telegram_staff_action_adapter_service import (
    TelegramStaffActionAdapterService,
)
from app.services.telegram_staff_confirmation_token_service import (
    TelegramStaffConfirmationTokenService,
)
from app.services.telegram_staff_link_token_service import TelegramStaffLinkTokenService

router = APIRouter()
logger = logging.getLogger(__name__)

PATIENT_MINI_APP_ENTRY_ROUTE = "/telegram/mini-app/patient"
PATIENT_PAYMENT_ENTRY_ROUTE = f"{PATIENT_MINI_APP_ENTRY_ROUTE}?section=payments"
PATIENT_BOOKING_ENTRY_ROUTE = f"{PATIENT_MINI_APP_ENTRY_ROUTE}?section=appointments"
PATIENT_FORMS_ENTRY_ROUTE = f"{PATIENT_MINI_APP_ENTRY_ROUTE}?section=forms"
PATIENT_BOOKING_ENTRY_CONTRACT = {
    "contract_version": "patient-booking-entrypoint-v1",
    "route": PATIENT_BOOKING_ENTRY_ROUTE,
    "surface": "telegram_mini_app_frontend",
    "auth": "telegram_init_data_or_short_lived_entry_token",
    "required_role": None,
    "contains_internal_identifiers": False,
    "telegram_url_parameters_allowed": False,
    "local_http_fallback": "signed_entry_token_from_bot_button",
    "entrypoint_type": "mini_app_web_app_button",
    "button_transport": "web_app_when_https_url_else_url_fallback",
}
PATIENT_PAYMENT_ENTRY_CONTRACT = {
    "contract_version": "patient-payment-entry-v1",
    "route": PATIENT_PAYMENT_ENTRY_ROUTE,
    "surface": "telegram_mini_app_frontend",
    "auth": "telegram_init_data_or_short_lived_entry_token",
    "required_role": None,
    "contains_internal_identifiers": False,
    "telegram_url_parameters_allowed": False,
    "local_http_fallback": "signed_entry_token_from_bot_button",
    "entrypoint_type": "mini_app_web_app_button",
    "button_transport": "web_app_when_https_url_else_url_fallback",
}
PATIENT_FORMS_ENTRY_CONTRACT = {
    "contract_version": "patient-forms-entrypoint-v1",
    "route": PATIENT_FORMS_ENTRY_ROUTE,
    "surface": "telegram_mini_app_frontend",
    "auth": "telegram_init_data_or_short_lived_entry_token",
    "required_role": None,
    "contains_internal_identifiers": False,
    "telegram_url_parameters_allowed": False,
    "local_http_fallback": "signed_entry_token_from_bot_button",
    "entrypoint_type": "mini_app_web_app_button",
    "button_transport": "web_app_when_https_url_else_url_fallback",
}
PATIENT_MINI_APP_MANIFEST_ENDPOINT = "/api/v1/telegram/mini-app/patient/manifest"
PATIENT_MINI_APP_MANIFEST_CONTRACT = {
    "contract_version": "patient-mini-app-manifest-v1",
    "endpoint": PATIENT_MINI_APP_MANIFEST_ENDPOINT,
    "surface": "telegram_mini_app_backend",
    "auth": "telegram_init_data_or_short_lived_entry_token",
    "scope": "linked_patient",
    "local_http_fallback": "signed_entry_token_from_bot_button",
    "entry_token_ttl_seconds": 600,
    "status": "manifest_only",
    "mutation_enabled": False,
    "contains_medical_data": False,
    "contains_payment_records": False,
    "contains_provider_payloads": False,
    "contains_report_files": False,
}

TELEGRAM_AI_APPROVAL_OUTCOMES = {"accepted", "rejected"}
TELEGRAM_AI_APPROVAL_REASON_CODES = {
    "accurate",
    "incomplete",
    "unsafe",
    "not_relevant",
    "workflow_issue",
    "other",
}
TELEGRAM_AI_APPROVAL_WORKFLOWS = {
    "doctor_draft_review": {
        "label": "Doctor AI draft review",
        "notification_type": "doctor_draft_review",
        "recipient_roles": ["doctor"],
        "outcome_roles": ["doctor"],
        "protected_route": "/doctor?tab=ai",
        "protected_surface": "EMR",
        "telegram_title": "AI draft is ready for protected review",
        "telegram_body": (
            "Open the protected EMR to review, edit, accept, or reject the AI draft."
        ),
        "allowed_metric_keys": ["draft_count"],
        "medical_workflow": True,
    },
    "queue_overload_alert": {
        "label": "Queue overload suggestion",
        "notification_type": "queue_overload",
        "recipient_roles": ["admin", "registrar"],
        "outcome_roles": ["admin", "registrar"],
        "protected_route": "/registrar?tab=queue",
        "protected_surface": "queue_dashboard",
        "telegram_title": "Queue overload suggestion",
        "telegram_body": (
            "Open the protected dashboard to review queue load and decide next steps."
        ),
        "allowed_metric_keys": [
            "waiting_count",
            "average_wait_minutes",
            "overloaded_services_count",
        ],
        "medical_workflow": False,
    },
    "payment_anomaly_alert": {
        "label": "Payment anomaly alert",
        "notification_type": "payment_anomaly",
        "recipient_roles": ["admin", "cashier"],
        "outcome_roles": ["admin", "cashier"],
        "protected_route": "/cashier?tab=payments",
        "protected_surface": "payment_dashboard",
        "telegram_title": "Payment anomaly needs review",
        "telegram_body": (
            "Open the protected dashboard to review payment reconciliation details."
        ),
        "allowed_metric_keys": [
            "unmatched_count",
            "provider_count",
            "difference_amount",
            "currency",
        ],
        "medical_workflow": False,
    },
    "owner_daily_summary": {
        "label": "Owner daily AI summary",
        "notification_type": "owner_daily_summary",
        "recipient_roles": ["admin", "owner"],
        "outcome_roles": ["admin", "owner"],
        "protected_route": "/admin/analytics",
        "protected_surface": "admin_analytics",
        "telegram_title": "Daily AI operations summary",
        "telegram_body": (
            "Review high-level clinic metrics in the protected dashboard."
        ),
        "allowed_metric_keys": [
            "revenue_total",
            "average_wait_minutes",
            "overloaded_services_count",
            "unpaid_visits_count",
            "integration_issue_count",
        ],
        "medical_workflow": False,
    },
}
TELEGRAM_AI_APPROVAL_CONTRACT = {
    "contract_version": "telegram-ai-approval-flows-v1",
    "enabled": True,
    "notification_runtime_enabled": True,
    "outcome_capture_enabled": True,
    "surface": "telegram_staff_notification_to_protected_app",
    "protected_links_required": True,
    "plain_chat_medical_content_allowed": False,
    "telegram_url_parameters_allowed": False,
    "requires_human_confirmation": True,
    "autonomous_mutation_allowed": False,
    "domain_mutations_performed_by_telegram_ai": False,
    "audit_action": "telegram_ai_approval_outcome_recorded",
    "notification_audit_action": "telegram_ai_approval_notification_sent",
    "outcomes": sorted(TELEGRAM_AI_APPROVAL_OUTCOMES),
    "workflows": [
        {
            "key": key,
            "label": workflow["label"],
            "notification_type": workflow["notification_type"],
            "recipient_roles": workflow["recipient_roles"],
            "outcome_roles": workflow["outcome_roles"],
            "protected_route": workflow["protected_route"],
            "protected_surface": workflow["protected_surface"],
            "allowed_metric_keys": workflow["allowed_metric_keys"],
            "medical_workflow": workflow["medical_workflow"],
            "plain_chat_medical_content_allowed": False,
            "autonomous_mutation_allowed": False,
        }
        for key, workflow in TELEGRAM_AI_APPROVAL_WORKFLOWS.items()
    ],
}

STAFF_LINK_TOKEN_PREFIX = "stl"
STAFF_LINK_TOKEN_HASH_PREFIX = "staff_link_token:"
STAFF_LINK_TOKEN_SEPARATOR = "_"
STAFF_BOT_TOKEN_ENV_KEYS = (
    "TELEGRAM_STAFF_BOT_TOKEN",
    "STAFF_TELEGRAM_BOT_TOKEN",
)
STAFF_BOT_TOKEN_SETTING_KEYS = (
    "staff_bot_token",
    "telegram_staff_bot_token",
)

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
        "ready": True,
    },
    {
        "key": "server_side_authorization",
        "label": "Проверка ролей на backend",
        "ready": True,
    },
    {
        "key": "read_only_menu_runtime",
        "label": "Read-only staff menu runtime",
        "ready": True,
    },
    {
        "key": "audit_logging",
        "label": "Аудит действий сотрудников",
        "ready": True,
    },
    {
        "key": "state_change_confirmations",
        "label": "Подтверждения для операций",
        "ready": True,
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
STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS = [
    "staff_readiness",
    "queue_overview",
    "next_patient",
    "today_schedule",
    "emr_reminders",
    "unpaid_invoices",
    "paid_invoices",
    "reconciliation_alerts",
    "payment_status",
    "ready_reports",
    "pending_reports",
    "delivery_status",
    "integration_errors",
    "revenue_summary",
    "daily_summary",
]

STAFF_BOT_TOKEN_CONTRACT = {
    "contract_version": "staff-token-v1",
    "enabled": False,
    "runtime_read_enabled": True,
    "required_before_enablement": True,
    "scope": "dedicated_staff_bot",
    "must_not_share_patient_bot_token": True,
    "secret_source": "environment_or_secret_store",
    "env_keys": list(STAFF_BOT_TOKEN_ENV_KEYS),
    "setting_keys": list(STAFF_BOT_TOKEN_SETTING_KEYS),
    "token_returned_to_frontend": False,
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
    "enabled": True,
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
            "status": "runtime_enabled",
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
    "enabled": True,
    "helper_available": True,
    "runtime_handler_enabled": True,
    "write_helper": "_upsert_staff_link_telegram_user",
    "legacy_write_helper": "link_staff_user_to_telegram",
    "lookup_helpers": [
        "get_telegram_user_by_chat_id",
        "get_telegram_user_by_linked_user_id",
    ],
    "writes": [
        "telegram_users.user_id",
        "audit_logs",
    ],
    "runtime_handler": "_handle_staff_link_start",
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
    "enabled": True,
    "migration_created": True,
    "runtime_write_enabled": True,
    "table": "telegram_staff_link_tokens",
    "raw_token_storage_allowed": False,
    "migration_revision": "0025_telegram_staff_link_tokens",
    "repository": "TelegramStaffLinkTokenRepository",
    "service": "TelegramStaffLinkTokenService",
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
    "enabled": True,
    "validator_enabled": True,
    "runtime_helper_available": True,
    "signature_validator_available": True,
    "expiry_validator_available": True,
    "binding_parser_available": True,
    "stateless_validator_enabled": False,
    "single_use_enforcement_enabled": True,
    "token_storage_enabled": True,
    "handler_enabled": True,
    "storage_migration_required": False,
    "storage_contract": STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT,
    "runtime_blocked_by": [],
    "required_before_enablement": True,
    "token_format": "stl_<user_id>_<chat_id>_<expires_at>_<nonce>_<signature>",
    "builder": "build_staff_link_start_token",
    "issuer": "issue_staff_link_start_token",
    "parser": "parse_staff_link_start_token",
    "validator": "validate_staff_link_start_token",
    "consumer": "TelegramStaffLinkTokenService.consume_for_validation",
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
        "token_not_issued",
        "token_binding_mismatch",
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

STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT = {
    "contract_version": "staff-confirmation-token-storage-v1",
    "enabled": True,
    "migration_created": True,
    "model_registered": True,
    "runtime_write_enabled": True,
    "runtime_consume_enabled": True,
    "table": "telegram_staff_confirmation_tokens",
    "raw_token_storage_allowed": False,
    "migration_revision": "0026_tg_staff_confirm_tokens",
    "repository": "TelegramStaffConfirmationTokenRepository",
    "service": "TelegramStaffConfirmationTokenService",
    "columns": [
        "id",
        "token_hash",
        "staff_user_id",
        "telegram_chat_id",
        "operation_key",
        "command_key",
        "action_payload_hash",
        "target_type",
        "target_reference_hash",
        "idempotency_key_hash",
        "expires_at",
        "consumed_at",
        "created_at",
        "request_id",
    ],
    "required_indexes": [
        "unique(token_hash)",
        "index(staff_user_id)",
        "index(telegram_chat_id)",
        "index(operation_key)",
        "partial_index(expires_at) where consumed_at is null",
    ],
    "required_constraints": [
        "expires_at > created_at",
        "consumed_at is null or consumed_at <= expires_at",
        "operation_key is not empty",
        "action_payload_hash is not empty",
        "staff_user_id references users(id)",
    ],
    "retention_policy": {
        "expired_token_ttl_days": 7,
        "consumed_token_ttl_days": 30,
    },
}

STAFF_BOT_AUTHORIZATION_CONTRACT = {
    "contract_version": "staff-authorization-v1",
    "enabled": True,
    "runtime_read_only_enabled": True,
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
    "registration_endpoint_published": True,
    "runtime_registration_enabled": True,
    "registration_endpoint": "POST /api/v1/admin/telegram/register-staff-commands",
    "runtime_handler": "register_staff_bot_commands",
    "telegram_api_method": "setMyCommands",
    "bot_scope": "staff_bot_only",
    "registered_command_scope": "read_only_staff_commands_only",
    "patient_bot_token_allowed": False,
    "uses_dedicated_staff_bot_token": True,
    "token_returned_to_frontend": False,
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
    "read_only_commands_registered": False,
    "enablement_gate": [
        "dedicated_staff_bot_token",
        "role_based_staff_linking",
        "server_side_authorization",
        "audit_logging",
        "state_change_confirmations",
    ],
    "state_changing_commands_registered": False,
}

STAFF_BOT_DOMAIN_ADAPTER_CONTRACT = {
    "contract_version": "staff-action-domain-adapters-v1",
    "enabled": True,
    "runtime_enabled": True,
    "required_before_state_change_enablement": True,
    "adapters": [
        {
            "operation_key": "queue_call_or_skip_patient",
            "adapter_key": "staff_queue_call_or_skip_adapter",
            "domain": "queue",
            "domain_service_required": "queue",
            "telegram_commands": ["/call", "/skip"],
            "runtime_enabled": True,
            "runtime_owner": "QueueBusinessService",
            "runtime_methods": [
                "staff_call_next_patient",
                "staff_skip_queue_entry",
            ],
            "protected_confirmation_runtime_owner": "TelegramStaffActionAdapterService",
            "protected_confirmation_runtime_methods": [
                "staff_call_next_patient",
                "staff_skip_queue_entry",
            ],
            "required_before_enablement": True,
            "required_runtime_checks": [
                "queue_target_resolved_server_side",
                "queue_domain_service_authorizes_target",
                "queue_time_not_rewritten",
                "idempotency_key_consumed_once",
                "staff_action_confirmed_audit_written",
                "staff_action_completed_or_failed_audit_written",
            ],
            "blocked_by": [
                "explicit_action_enablement",
            ],
        },
        {
            "operation_key": "visit_cancel_or_move",
            "adapter_key": "staff_queue_visit_cancel_or_move_adapter",
            "domain": "queue",
            "domain_service_required": "visit",
            "telegram_commands": ["/cancel_visit", "/move_visit"],
            "runtime_enabled": True,
            "runtime_scope": "visit_record_and_queue_link_status",
            "runtime_owner": "TelegramStaffActionAdapterService",
            "runtime_methods": [
                "staff_cancel_visit",
                "staff_move_visit",
            ],
            "queue_link_runtime_owner": "QueueBusinessService",
            "queue_link_runtime_methods": [
                "staff_cancel_visit_queue_link",
                "staff_move_visit_queue_link",
            ],
            "visit_record_mutation_enabled": True,
            "required_before_enablement": True,
            "required_runtime_checks": [
                "visit_target_resolved_server_side",
                "queue_entry_resolved_server_side",
                "visit_domain_service_authorizes_target",
                "queue_fairness_not_reordered",
                "queue_time_not_rewritten",
                "idempotency_key_consumed_once",
                "staff_action_confirmed_audit_written",
                "staff_action_completed_or_failed_audit_written",
            ],
            "blocked_by": [
                "explicit_action_enablement",
            ],
        },
        {
            "operation_key": "payment_status_change",
            "adapter_key": "staff_payment_status_change_adapter",
            "domain": "payment",
            "domain_service_required": "payment",
            "telegram_commands": ["/payment_status"],
            "runtime_enabled": True,
            "runtime_owner": "TelegramStaffActionAdapterService",
            "runtime_methods": ["staff_change_payment_status"],
            "required_before_enablement": True,
            "required_runtime_checks": [
                "payment_target_resolved_in_protected_app",
                "payment_status_transition_validated_by_billing_service",
                "idempotency_key_consumed_once",
                "staff_action_confirmed_audit_written",
                "staff_action_completed_or_failed_audit_written",
            ],
            "blocked_by": ["explicit_action_enablement"],
        },
        {
            "operation_key": "refund_issue",
            "adapter_key": "staff_payment_refund_adapter",
            "domain": "payment",
            "domain_service_required": "payment",
            "telegram_commands": ["/refund"],
            "runtime_enabled": True,
            "runtime_owner": "TelegramStaffActionAdapterService",
            "runtime_methods": ["staff_refund_payment"],
            "required_before_enablement": True,
            "required_runtime_checks": [
                "payment_target_resolved_in_protected_app",
                "refund_amount_within_available_balance",
                "refund_policy_allows_payment_status",
                "idempotency_key_consumed_once",
                "staff_action_confirmed_audit_written",
                "staff_action_completed_or_failed_audit_written",
            ],
            "blocked_by": ["explicit_action_enablement"],
        },
        {
            "operation_key": "doctor_schedule_change",
            "adapter_key": "staff_schedule_change_adapter",
            "domain": "schedule",
            "domain_service_required": "schedule",
            "telegram_commands": ["/change_schedule"],
            "runtime_enabled": True,
            "runtime_owner": "TelegramStaffActionAdapterService",
            "runtime_methods": ["staff_change_doctor_schedule"],
            "required_before_enablement": True,
            "required_runtime_checks": [
                "schedule_target_resolved_in_protected_app",
                "schedule_time_range_validated",
                "idempotency_key_consumed_once",
                "staff_action_confirmed_audit_written",
                "staff_action_completed_or_failed_audit_written",
            ],
            "blocked_by": ["explicit_action_enablement"],
        },
    ],
    "blocked_by": [
        "explicit_action_enablement",
    ],
}

STAFF_BOT_ACTION_ENABLEMENT_CONTRACT = {
    "contract_version": "staff-action-enablements-v1",
    "enabled": True,
    "surface": "protected_app_confirmation_endpoint",
    "telegram_callback_execution_enabled": False,
    "telegram_message_execution_enabled": False,
    "protected_action_execution_enabled": True,
    "enabled_commands": [
        "/call",
        "/skip",
        "/cancel_visit",
        "/move_visit",
        "/payment_status",
        "/refund",
        "/change_schedule",
    ],
    "disabled_commands": [
        "/publish_document",
    ],
    "enablement_rule": (
        "Commands are enabled one by one only after target binding, "
        "idempotency consumption, audit, and focused runtime tests exist."
    ),
    "enabled_runtime_owner": "TelegramStaffActionAdapterService",
    "enabled_runtime_methods": [
        "staff_call_next_patient",
        "staff_skip_queue_entry",
        "staff_cancel_visit",
        "staff_move_visit",
        "staff_change_payment_status",
        "staff_refund_payment",
        "staff_change_doctor_schedule",
    ],
    "required_before_command_enablement": [
        "domain_adapter_runtime_enabled",
        "role_rechecked_in_protected_app",
        "fresh_confirmation_token_consumed_once",
        "staff_action_confirmed_audit_written",
        "staff_action_completed_or_failed_audit_written",
    ],
}

STAFF_BOT_CONFIRMATION_CONTRACT = {
    "contract_version": "staff-confirmations-v1",
    "enabled": True,
    "required_for_state_changes": True,
    "runtime_guard_enabled": True,
    "deny_only_runtime_enabled": False,
    "confirmation_request_runtime_enabled": True,
    "confirmation_requests_create_tokens": True,
    "state_change_command_guard_enabled": True,
    "confirmation_token_runtime_enabled": True,
    "idempotency_request_hash_runtime_enabled": True,
    "idempotency_key_returned_to_telegram": False,
    "state_changing_actions_enabled": False,
    "protected_action_execution_enabled": True,
    "action_enablement_contract": STAFF_BOT_ACTION_ENABLEMENT_CONTRACT,
    "confirmation_window_seconds": 120,
    "default_state_change_decision": "deny_until_domain_adapters_and_action_enablement",
    "token_storage_contract": STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT,
    "domain_adapter_contract": STAFF_BOT_DOMAIN_ADAPTER_CONTRACT,
    "operations": [
        {
            "key": "queue_call_or_skip_patient",
            "label": "Вызвать или пропустить пациента",
            "roles": ["registrar"],
            "domain_service_required": "queue",
            "telegram_commands": ["/call", "/skip"],
        },
        {
            "key": "visit_cancel_or_move",
            "label": "Отменить или перенести визит",
            "roles": ["registrar", "admin"],
            "domain_service_required": "visit",
            "telegram_commands": ["/cancel_visit", "/move_visit"],
        },
        {
            "key": "payment_status_change",
            "label": "Изменить статус оплаты",
            "roles": ["cashier", "admin"],
            "domain_service_required": "payment",
            "telegram_commands": ["/payment_status"],
        },
        {
            "key": "refund_issue",
            "label": "Оформить возврат",
            "roles": ["cashier", "admin", "owner"],
            "domain_service_required": "payment",
            "telegram_commands": ["/refund"],
        },
        {
            "key": "medical_document_publish",
            "label": "Закрыть ЭМК или опубликовать документ",
            "roles": ["doctor", "lab", "admin"],
            "domain_service_required": "emr_or_lab",
            "telegram_commands": ["/publish_document"],
        },
        {
            "key": "doctor_schedule_change",
            "label": "Изменить расписание врача",
            "roles": ["admin", "owner"],
            "domain_service_required": "schedule",
            "telegram_commands": ["/change_schedule"],
        },
    ],
    "required_server_checks": [
        "staff_linked_to_active_application_user",
        "role_allowed_for_operation",
        "state_changing_action_registered",
        "fresh_confirmation_token",
        "idempotency_key_present",
        "domain_service_authorizes_target",
        "audit_log_write_succeeds",
    ],
    "runtime_blocked_by": [
        "domain_service_action_adapters",
        "explicit_action_enablement",
    ],
    "telegram_payload_rules": [
        "no_raw_internal_ids",
        "no_plain_medical_details",
        "short_human_readable_summary_only",
    ],
}

STAFF_BOT_AUDIT_CONTRACT = {
    "contract_version": "staff-audit-v1",
    "enabled": True,
    "record_writer_enabled": True,
    "runtime_read_only_enabled": True,
    "read_only_menu_events_enabled": True,
    "state_change_denial_events_enabled": True,
    "confirmation_request_events_enabled": True,
    "state_change_events_enabled": True,
    "required_state_change_event_types": [
        "staff_action_confirmed",
        "staff_action_completed",
        "staff_action_failed",
    ],
    "recorded_event_types": [
        "staff_link_created",
        "staff_link_token_rejected",
        "staff_command_received",
        "staff_action_denied",
        "staff_action_confirmation_requested",
        "staff_action_confirmed",
        "staff_action_completed",
        "staff_action_failed",
    ],
    "pending_event_types": [],
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
            "key": "staff_action_completed",
            "label": "Completed staff action after confirmed domain execution",
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
        "no_raw_staff_command_text",
        "no_plain_medical_details",
        "no_raw_internal_identifiers_in_chat_text",
    ],
}

STAFF_BOT_ROLE_MENU_ENABLEMENT_CONTRACT = {
    "contract_version": "staff-role-menu-enablement-v1",
    "enabled": True,
    "runtime_menu_enabled": True,
    "read_only_contract_published": True,
    "required_before_enablement": True,
    "state_changing_menu_items_enabled": False,
    "runtime_handler": "_handle_staff_read_only_menu",
    "domain_data_commands_enabled": True,
    "domain_data_commands_status": "complete",
    "domain_data_command_keys": list(STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS),
    "pending_domain_data_command_keys": [],
    "state_changing_actions_enabled": False,
    "allowed_until_enabled": [
        "read_status_contract",
        "read_only_menu_runtime",
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
        expires_at = expires_at.replace(tzinfo=UTC)
    else:
        expires_at = expires_at.astimezone(UTC)
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


def issue_staff_link_start_token(
    db: Session,
    *,
    user_id: int,
    chat_id: int,
    expires_at: datetime,
    issued_by_user_id: int | None = None,
    request_id: str | None = None,
    nonce: str | None = None,
) -> str:
    token = build_staff_link_start_token(
        user_id=user_id,
        chat_id=chat_id,
        expires_at=expires_at,
        nonce=nonce,
    )
    token_hash = _hash_staff_link_start_token(token)
    TelegramStaffLinkTokenService(db).issue_token(
        token_hash=token_hash,
        staff_user_id=user_id,
        telegram_chat_id=chat_id,
        expires_at=expires_at,
        issued_by_user_id=issued_by_user_id,
        request_id=request_id,
    )
    logger.info(
        "Issued stored Telegram staff link token user_id=%s chat_id=%s",
        user_id,
        chat_id,
    )
    return token


def _decode_staff_link_start_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
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
            tz=UTC,
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
    if expires_at < datetime.now(UTC):
        return decoded, "expired"
    return decoded, None


def parse_staff_link_start_token(token: str) -> dict[str, Any] | None:
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
    db: Session,
    token: str,
    telegram_chat_id: int,
    *,
    enforce_single_use: bool = True,
) -> dict[str, Any]:
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

    single_use_enforced = False
    consumed_at = None
    if enforce_single_use:
        consume_result = TelegramStaffLinkTokenService(db).consume_for_validation(
            token_hash=parsed["token_hash"],
            staff_user_id=int(user.id),
            telegram_chat_id=int(parsed["chat_id"]),
        )
        if not consume_result.get("valid"):
            return {
                "valid": False,
                "reason": consume_result.get("reason", "already_used"),
                "token_hash": parsed["token_hash"],
            }
        single_use_enforced = bool(consume_result.get("single_use_enforced"))
        consumed_at = consume_result.get("consumed_at")

    logger.info("Staff Telegram link token validated role=%s", role_key)
    result = {
        "valid": True,
        "reason": "ok",
        "token_hash": parsed["token_hash"],
        "user_id": int(user.id),
        "chat_id": int(parsed["chat_id"]),
        "role": role_key,
        "expires_at": parsed["expires_at"].isoformat(),
        "single_use_enforced": single_use_enforced,
    }
    if consumed_at:
        result["consumed_at"] = consumed_at
    return result


def _build_staff_role_menus_summary() -> dict[str, Any]:
    menu_roles = [
        role_menu["role"] for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT
    ]
    menu_item_count = sum(
        len(role_menu.get("items", []))
        for role_menu in STAFF_BOT_READ_ONLY_MENU_CONTRACT
    )
    return {
        "contract_published": True,
        "runtime_enabled": True,
        "read_only": True,
        "source": "read_only_menu_contract",
        "roles": menu_roles,
        "role_count": len(menu_roles),
        "item_count": menu_item_count,
        "handler": "_handle_staff_read_only_menu",
        "domain_data_commands_enabled": True,
        "domain_data_commands_status": "complete",
        "domain_data_command_keys": list(STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS),
        "state_changing_actions_enabled": False,
        "blocked_until": [],
    }


def _build_staff_role_menu_enablement_contract(
    role_menus: dict[str, Any],
) -> dict[str, Any]:
    return {
        **STAFF_BOT_ROLE_MENU_ENABLEMENT_CONTRACT,
        "roles_covered": role_menus["roles"],
        "role_count": role_menus["role_count"],
        "menu_item_count": role_menus["item_count"],
    }


def _build_staff_bot_next_slice(token_contract: dict[str, Any]) -> str:
    if not token_contract["ready"]:
        return "dedicated_staff_bot_token_runtime_config"

    pending_domain_keys = STAFF_BOT_ROLE_MENU_ENABLEMENT_CONTRACT.get(
        "pending_domain_data_command_keys"
    ) or []
    if pending_domain_keys:
        return f"staff_read_only_{pending_domain_keys[0]}_runtime"

    confirmation_blockers = (
        STAFF_BOT_CONFIRMATION_CONTRACT.get("runtime_blocked_by") or []
    )
    if confirmation_blockers:
        return f"staff_state_change_{confirmation_blockers[0]}"

    return "staff_read_only_domain_data_runtime_complete"


def _build_staff_bot_status(
    webhook_set: bool, staff_bot_token_status: dict[str, Any] | None = None
) -> dict[str, Any]:
    role_menus = _build_staff_role_menus_summary()
    token_status = staff_bot_token_status or {
        "configured": False,
        "ready": False,
        "source": "not_configured",
        "source_key": None,
    }
    token_contract = _build_staff_bot_token_contract(token_status)
    command_registration_contract = _build_staff_command_registration_contract(
        token_contract
    )
    return {
        "version": "linking-runtime",
        "contract_version": "staff-menu-read-only-v1",
        "enabled": False,
        "contract_published": True,
        "read_only_runtime_enabled": True,
        "status": "staff_read_only_menu_enabled_actions_disabled",
        "transport": "polling" if not webhook_set else "webhook",
        "supported_languages": [
            {"code": "ru", "label": "Русский"},
        ],
        "supported_roles": STAFF_BOT_SUPPORTED_ROLES,
        "role_linking": {
            "enabled": True,
            "required_before_enablement": True,
            "runtime_handler_enabled": True,
            "accepted_methods": [
                "admin_verified_staff_link",
                "one_time_signed_staff_token",
            ],
        },
        "token_contract": token_contract,
        "linking_contract": STAFF_BOT_LINKING_CONTRACT,
        "linking_runtime_contract": STAFF_BOT_LINKING_RUNTIME_CONTRACT,
        "link_token_validation_contract": STAFF_BOT_LINK_TOKEN_VALIDATION_CONTRACT,
        "link_token_storage_contract": STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT,
        "confirmation_token_storage_contract": (
            STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT
        ),
        "authorization_contract": STAFF_BOT_AUTHORIZATION_CONTRACT,
        "command_registration_contract": command_registration_contract,
        "confirmation_contract": STAFF_BOT_CONFIRMATION_CONTRACT,
        "domain_adapter_contract": STAFF_BOT_DOMAIN_ADAPTER_CONTRACT,
        "audit_contract": STAFF_BOT_AUDIT_CONTRACT,
        "authorization": {
            "source": "application_rbac",
            "server_side_required": True,
            "ready": True,
            "runtime_read_only_enabled": True,
            "default_decision": "deny",
        },
        "audit": {
            "required": True,
            "ready": True,
            "linking_events_ready": True,
            "staff_command_events_ready": True,
            "read_only_menu_events_ready": True,
            "state_change_denial_events_ready": True,
            "confirmation_request_events_ready": True,
            "state_change_events_ready": True,
            "required_state_change_event_types": list(
                STAFF_BOT_AUDIT_CONTRACT["required_state_change_event_types"]
            ),
            "pending_state_change_event_types": list(
                STAFF_BOT_AUDIT_CONTRACT.get("pending_event_types") or []
            ),
        },
        "confirmations": {
            "required": True,
            "ready": True,
            "runtime_guard_enabled": True,
            "deny_only_runtime_enabled": False,
            "confirmation_request_runtime_enabled": True,
            "confirmation_requests_create_tokens": True,
            "state_change_command_guard_enabled": True,
            "confirmation_token_runtime_enabled": True,
            "idempotency_request_hash_runtime_enabled": True,
            "idempotency_key_returned_to_telegram": False,
            "domain_adapter_runtime_enabled": True,
            "queue_action_adapter_runtime_enabled": True,
            "visit_queue_link_adapter_runtime_enabled": True,
            "protected_action_execution_enabled": True,
            "enabled_commands": list(
                STAFF_BOT_ACTION_ENABLEMENT_CONTRACT["enabled_commands"]
            ),
            "telegram_callback_execution_enabled": False,
            "domain_adapter_blockers": list(
                STAFF_BOT_DOMAIN_ADAPTER_CONTRACT["blocked_by"]
            ),
            "state_changing_actions_enabled": False,
            "default_state_change_decision": (
                "deny_until_domain_adapters_and_action_enablement"
            ),
        },
        "action_enablement_contract": STAFF_BOT_ACTION_ENABLEMENT_CONTRACT,
        "state_changing_actions_enabled": False,
        "readiness": STAFF_BOT_READINESS,
        "role_menus": role_menus,
        "role_menu_enablement_contract": (
            _build_staff_role_menu_enablement_contract(role_menus)
        ),
        "read_only_menu_contract": STAFF_BOT_READ_ONLY_MENU_CONTRACT,
        "guardrails": STAFF_BOT_GUARDRAILS,
        "next_slice": _build_staff_bot_next_slice(token_contract),
    }


def _staff_runtime_reference_hash(kind: str, value: Any) -> str:
    digest = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()
    return f"{kind}:{digest[:24]}"


def _telegram_ai_approval_reference_hash(value: Any) -> str:
    digest = hashlib.sha256(
        f"telegram_ai_approval:{value}".encode()
    ).hexdigest()
    return f"telegram_ai_approval:{digest[:24]}"


def _telegram_ai_approval_workflow(workflow_key: str) -> dict[str, Any]:
    key = str(workflow_key or "").strip().lower()
    workflow = TELEGRAM_AI_APPROVAL_WORKFLOWS.get(key)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unsupported_ai_approval_workflow",
        )
    return workflow


def _protected_frontend_url(route: str) -> str | None:
    frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip()
    if not frontend_url:
        return None
    if not frontend_url.startswith(("https://", "http://")):
        return None
    normalized_route = str(route or "").strip()
    if not normalized_route.startswith("/"):
        normalized_route = f"/{normalized_route}"
    return f"{frontend_url.rstrip('/')}{normalized_route}"


def _safe_ai_approval_value(value: Any) -> str:
    if isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, (int, float, Decimal)):
        text = str(value)
    else:
        text = str(value or "").strip()
    return escape(text[:80])


def _safe_ai_approval_metrics(
    workflow: dict[str, Any], metrics: dict[str, Any] | None
) -> dict[str, str]:
    if not isinstance(metrics, dict):
        return {}
    allowed_keys = {str(key) for key in workflow.get("allowed_metric_keys", [])}
    safe_metrics: dict[str, str] = {}
    for key in sorted(allowed_keys):
        if key in metrics:
            safe_metrics[key] = _safe_ai_approval_value(metrics.get(key))
    return safe_metrics


def build_telegram_ai_approval_message(
    workflow_key: str,
    protected_url: str,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a PHI-free Telegram AI approval message with only a protected link."""

    workflow = _telegram_ai_approval_workflow(workflow_key)
    safe_metrics = _safe_ai_approval_metrics(workflow, metrics)
    lines = [
        str(workflow["telegram_title"]),
        "",
        str(workflow["telegram_body"]),
        "Telegram does not show diagnosis, EMR text, documents, or internal IDs.",
    ]
    if safe_metrics:
        lines.append("")
        lines.append("Safe metrics:")
        for key, value in safe_metrics.items():
            lines.append(f"- {key}: {value}")

    return {
        "workflow_key": str(workflow_key).strip().lower(),
        "text": "\n".join(lines),
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Open protected clinic app", "url": protected_url}]
            ]
        },
        "protected_route": workflow["protected_route"],
        "safe_metric_keys": sorted(safe_metrics),
        "contains_plain_chat_medical_content": False,
        "autonomous_mutation_allowed": False,
        "requires_human_confirmation": True,
    }


def _build_telegram_ai_approval_status() -> dict[str, Any]:
    return {
        **TELEGRAM_AI_APPROVAL_CONTRACT,
        "workflow_count": len(TELEGRAM_AI_APPROVAL_WORKFLOWS),
        "runtime_guardrails": [
            "protected_link_only",
            "safe_metric_allowlist",
            "hash_only_target_reference",
            "accepted_rejected_outcome_audit",
            "no_autonomous_domain_mutation",
        ],
    }


def _assert_ai_approval_role_allowed(
    workflow: dict[str, Any],
    role: Any,
    *,
    role_field: str,
) -> None:
    normalized_role = _normalize_staff_role(role)
    allowed_roles = {
        _normalize_staff_role(item) for item in workflow.get(role_field, [])
    }
    if normalized_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="role_not_allowed_for_ai_approval_workflow",
        )


def _normalize_ai_approval_outcome(outcome: Any) -> str:
    normalized = str(outcome or "").strip().lower()
    if normalized not in TELEGRAM_AI_APPROVAL_OUTCOMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unsupported_ai_approval_outcome",
        )
    return normalized


def _normalize_ai_approval_reason_code(reason_code: Any) -> str | None:
    normalized = str(reason_code or "").strip().lower()
    if not normalized:
        return None
    if normalized not in TELEGRAM_AI_APPROVAL_REASON_CODES:
        return "other"
    return normalized


class StaffActionConfirmRequest(BaseModel):
    entry_id: int | None = None
    visit_id: int | None = None
    new_visit_date: date | None = None
    payment_id: int | None = None
    new_status: str | None = None
    refund_amount: Decimal | None = None
    refund_reason: str | None = None
    schedule_id: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    breaks: list[dict[str, str]] | None = None
    active: bool | None = None


class TelegramAiApprovalAlertRequest(BaseModel):
    workflow_key: str
    recipient_user_id: int
    target_reference: str | None = None
    metrics: dict[str, Any] | None = None


class TelegramAiApprovalOutcomeRequest(BaseModel):
    workflow_key: str
    outcome: str
    target_reference: str | None = None
    reason_code: str | None = None


def _staff_state_change_operation_by_key(operation_key: str) -> dict[str, Any] | None:
    for operation in STAFF_BOT_CONFIRMATION_CONTRACT.get("operations", []):
        if str(operation.get("key") or "") == operation_key:
            return operation
    return None


def _record_staff_action_execution_failure(
    db: Session,
    *,
    record: TelegramStaffConfirmationToken | None,
    current_user: User,
    operation_key: str,
    command_key: str | None,
    reason: str,
) -> None:
    telegram_chat_id = getattr(record, "telegram_chat_id", None)
    payload = {
        "actor_user_id": current_user.id,
        "actor_role": _normalize_staff_role(getattr(current_user, "role", None)),
        "telegram_user_id_hash": (
            _staff_runtime_reference_hash("telegram_chat", telegram_chat_id)
            if telegram_chat_id is not None
            else None
        ),
        "action_key": "staff_action_failed",
        "operation_key": operation_key,
        "command_key": command_key,
        "target_type": "telegram_staff_action",
        "target_reference_hash": _staff_runtime_reference_hash(
            "telegram_staff_action",
            getattr(record, "id", operation_key),
        ),
        "result": "failed",
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
        "confirmation_required": True,
        "telegram_execution_enabled": False,
        "domain_mutation": False,
        "state_changing_action": True,
        "redacted": True,
    }
    crud_audit.log(
        db,
        action="staff_action_failed",
        entity_type="telegram_staff_action",
        entity_id=getattr(record, "id", None),
        actor_user_id=current_user.id,
        payload=payload,
    )


def _validate_staff_action_target_request(
    command_key: str,
    request: StaffActionConfirmRequest,
) -> str | None:
    command = command_key.lower()
    if command == "/call":
        return None
    if command == "/skip":
        return None if request.entry_id is not None else "entry_id_required"
    if command == "/cancel_visit":
        return None if request.visit_id is not None else "visit_id_required"
    if command == "/move_visit":
        if request.visit_id is None:
            return "visit_id_required"
        if request.new_visit_date is None:
            return "new_visit_date_required"
        return None
    if command == "/payment_status":
        if request.payment_id is None:
            return "payment_id_required"
        if not str(request.new_status or "").strip():
            return "new_status_required"
        return None
    if command == "/refund":
        return None if request.payment_id is not None else "payment_id_required"
    if command == "/change_schedule":
        if request.schedule_id is None:
            return "schedule_id_required"
        if (
            request.start_time is None
            and request.end_time is None
            and request.breaks is None
            and request.active is None
        ):
            return "schedule_change_required"
        return None
    return "command_executor_not_supported"


def _staff_action_expected_target_binding(
    command_key: str,
    request: StaffActionConfirmRequest,
) -> tuple[str, int] | None:
    command = command_key.lower()
    if command == "/call":
        return None
    if command == "/skip" and request.entry_id is not None:
        return ("queue_entry", int(request.entry_id))
    if command in {"/cancel_visit", "/move_visit"} and request.visit_id is not None:
        return ("visit", int(request.visit_id))
    if command in {"/payment_status", "/refund"} and request.payment_id is not None:
        return ("payment", int(request.payment_id))
    if command == "/change_schedule" and request.schedule_id is not None:
        return ("schedule", int(request.schedule_id))
    return None


def _validate_staff_action_target_binding(
    record: TelegramStaffConfirmationToken,
    command_key: str,
    request: StaffActionConfirmRequest,
) -> str | None:
    expected = _staff_action_expected_target_binding(command_key, request)
    if expected is None:
        return None

    target_type, target_id = expected
    expected_hash = _staff_runtime_reference_hash(target_type, target_id)
    if not record.target_reference_hash:
        return "target_binding_required"
    if str(record.target_type or "") != target_type:
        return "target_binding_mismatch"
    if str(record.target_reference_hash) != expected_hash:
        return "target_binding_mismatch"
    return None


# ============================================================
# === AI APPROVAL ENDPOINTS ===
# ============================================================
