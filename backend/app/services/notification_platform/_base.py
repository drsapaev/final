"""Backend-owned notification platform orchestration."""

from __future__ import annotations

import hashlib  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import re  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from typing import Any  # noqa: F401
from zoneinfo import ZoneInfo  # noqa: F401

from sqlalchemy import func, or_  # noqa: F401
from sqlalchemy.orm import Session, selectinload  # noqa: F401

from app.models.notification import (  # noqa: F401
    NotificationDelivery,
    NotificationEvent,
)
from app.models.patient import Patient  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_profile import UserProfile  # noqa: F401
from app.repositories.notification_platform_repository import (  # noqa: F401
    NotificationPlatformRepository,
)
from app.services.notification_websocket import (
    get_notification_ws_manager,  # noqa: F401
)

logger = logging.getLogger(__name__)



class NotificationPlatformServiceMixinBase:
    """Type-hint anchor with class-level constants."""


    INBOX_CHANNEL = "in_app_inbox"
    TRANSPORT_NOTIFICATION = "notification"
    TRANSPORT_QUEUE_UPDATE = "queue_update"
    TRANSPORT_SYSTEM_ALERT = "system_alert"
    DEFAULT_TIMEZONE = "Asia/Tashkent"

    CRITICAL_EVENT_TYPES = {
        "security_alert",
        "billing_alert",
        "lab_critical_result",
    }

    QUIET_HOURS_QUEUE_EVENT_TYPES = {
        "queue_update",
        "queue_changed",
        "queue_call",
        "queue_position",
        "queue_reminder",
        "diagnostics_return_needed",
        "diagnostics_return",
        "queue_status_changed",
    }

    QUEUE_BURST_SUPPRESSION_EVENT_TYPES = {
        "queue_update",
        "queue_changed",
        "queue_position",
        "queue_reminder",
        "diagnostics_return_needed",
        "diagnostics_return",
        "queue_status_changed",
    }
    QUEUE_BURST_SUPPRESSION_WINDOW_SECONDS = 45

    REALTIME_PUSH_SETTING_BY_EVENT_TYPE = {
        "appointment_reminder": "push_appointment_reminder",
        "appointment_confirmation": "push_appointment_confirmation",
        "visit_confirmation": "push_appointment_confirmation",
        "new_appointment": "push_appointment_confirmation",
        "schedule_change": "push_appointment_cancellation",
        "payment_notification": "push_payment_receipt",
        "security_alert": "push_security_alerts",
        "system_alert": "push_system_updates",
        "registrar_system_alert": "push_system_updates",
        "price_change": "push_system_updates",
        "all_free_requested": "push_system_updates",
        "all_free_approved": "push_system_updates",
        "all_free_rejected": "push_system_updates",
        "queue_update": "push_system_updates",
        "queue_call": "push_system_updates",
        "queue_position": "push_system_updates",
        "queue_reminder": "push_system_updates",
        "diagnostics_return_needed": "push_system_updates",
        "queue_status_changed": "push_system_updates",
        "patient_registered": "push_system_updates",
    }

    ROLE_ALIASES = {
        "admin": "admin",
        "cashier": "cashier",
        "doctor": "doctor",
        "lab": "lab",
        "labtechnician": "lab",
        "lab_technician": "lab",
        "patient": "patient",
        "registrar": "registrar",
        "receptionist": "registrar",
        "cardiologist": "cardiologist",
        "dermatologist": "dermatologist",
        "dentist": "dentist",
    }

    DEPARTMENT_ROLE_ALIASES = {
        "cardiology": "cardiologist",
        "cardiologist": "cardiologist",
        "dentistry": "dentist",
        "dental": "dentist",
        "dentist": "dentist",
        "dermatology": "dermatologist",
        "dermatologist": "dermatologist",
        "lab": "lab",
        "laboratory": "lab",
        "registrar": "registrar",
        "reception": "registrar",
        "receptionist": "registrar",
        "cashier": "cashier",
        "clinic": "doctor",
        "doctor": "doctor",
        "general": "doctor",
    }

    LEGACY_EVENT_TYPE_ALIASES = {
        "queue_changed": "queue_update",
        "diagnostics_return": "diagnostics_return_needed",
        "queue_status": "queue_status_changed",
        "payment_update": "payment_notification",
        "payment_success": "payment_notification",
        "result_ready": "lab_results",
        "lab_result_ready": "lab_results",
        "appointment_rescheduled": "schedule_change",
        "appointment_cancelled": "schedule_change",
        "all_free_pending": "all_free_requested",
        "all_free_declined": "all_free_rejected",
        "allfree_requested": "all_free_requested",
        "allfree_approved": "all_free_approved",
        "allfree_rejected": "all_free_rejected",
        "notification_message_received": "message_received",
        "lab_critical": "lab_critical_result",
        "lab_new_assignment": "lab_new_study",
        "lab_result_sent": "lab_result_sent_confirmation",
        "registrar_alert": "registrar_system_alert",
        "security_warning": "security_alert",
        "billing_warning": "billing_alert",
        "patient_create": "patient_registered",
    }

    EVENT_FAMILY_BY_TYPE = {
        "appointment_reminder": "appointment",
        "appointment_confirmation": "appointment",
        "visit_confirmation": "appointment",
        "schedule_change": "appointment",
        "new_appointment": "appointment",
        "payment_notification": "payment",
        "queue_update": "queue",
        "queue_call": "queue",
        "queue_position": "queue",
        "queue_reminder": "queue",
        "queue_status_changed": "queue",
        "diagnostics_return_needed": "queue",
        "lab_results": "lab",
        "lab_critical_result": "lab",
        "lab_new_study": "lab",
        "lab_critical_finding": "lab",
        "lab_result_sent_confirmation": "lab",
        "prescription_ready": "lab",
        "all_free_requested": "all_free",
        "all_free_approved": "all_free",
        "all_free_rejected": "all_free",
        "message_received": "message",
        "patient_registered": "patient",
        "system_alert": "system",
        "registrar_system_alert": "system",
        "price_change": "system",
        "security_alert": "security",
        "billing_alert": "billing",
    }



































































































