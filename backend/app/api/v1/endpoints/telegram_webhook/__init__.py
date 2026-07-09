"""
Telegram webhook package.

Re-exports router and shared symbols for backward compatibility with
tests and other modules that import from the package root.

Before the split into a package, telegram_webhook.py was a single file
with all these names at module level. Tests access them via
`telegram_webhook._some_function` — which requires explicit re-exports
because `from ... import *` does not pick up underscore-prefixed names.
"""
# Import endpoint modules to register routes on the shared router.
from app.api.v1.endpoints.telegram_webhook import (  # noqa: F401
    _clinic_bot,
    _patient_commands,
    _routes,
    _staff_commands,
)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._helpers import router  # noqa: F401

# Re-export underscore-prefixed symbols and constants that tests and
# other modules access via `telegram_webhook.<name>`.
from app.api.v1.endpoints.telegram_webhook._helpers import (  # noqa: F401
    PATIENT_BOOKING_ENTRY_ROUTE,
    PATIENT_MINI_APP_ENTRY_ROUTE,
    PATIENT_PAYMENT_ENTRY_ROUTE,
    TELEGRAM_CONTACT_REJECTED_MESSAGE,
    TELEGRAM_LANGUAGE_MENU,
    TELEGRAM_LOCALIZED_TEXTS,
    TELEGRAM_STAFF_LINKED_MESSAGE,
    TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
    TELEGRAM_STAFF_LINK_REPLY_MARKUP,
    TELEGRAM_TICKET_QR_PREFIX,
    _build_patient_onboarding_entry_token,
    _localized_main_menu,
    _localized_notification_consent_menu,
    _localized_services_menu,
    _localized_settings_menu,
    _localized_text,
    _normalize_patient_language,
    _parse_patient_mini_app_entry_token,
    _parse_patient_onboarding_entry_token,
    _telegram_settings_message,
)
from app.api.v1.endpoints.telegram_webhook._clinic_bot import (  # noqa: F401
    _handle_clinic_bot_update,
)
from app.api.v1.endpoints.telegram_webhook._patient_commands import (  # noqa: F401
    _send_patient_bot_reply,
)
from app.api.v1.endpoints.telegram_webhook._routes import (  # noqa: F401
    send_message_to_user,
)
from app.api.v1.endpoints.telegram_webhook._staff_commands import (  # noqa: F401
    _build_lab_report_pdf,
    _clinic_payments_message,
    _clinic_queue_message,
    _clinic_visits_message,
    _handle_contact_link,
    _handle_staff_link_start,
    _handle_staff_read_only_menu,
    _handle_ticket_qr_start,
    _latest_ready_lab_report_instances,
    _queue_entry_position,
    _send_clinic_lab_results,
)

__all__ = [
    "router",
    "send_message_to_user",
    # Constants
    "PATIENT_BOOKING_ENTRY_ROUTE",
    "PATIENT_MINI_APP_ENTRY_ROUTE",
    "PATIENT_PAYMENT_ENTRY_ROUTE",
    "TELEGRAM_CONTACT_REJECTED_MESSAGE",
    "TELEGRAM_LANGUAGE_MENU",
    "TELEGRAM_LOCALIZED_TEXTS",
    "TELEGRAM_STAFF_LINKED_MESSAGE",
    "TELEGRAM_STAFF_LINK_REJECTED_MESSAGE",
    "TELEGRAM_STAFF_LINK_REPLY_MARKUP",
    "TELEGRAM_TICKET_QR_PREFIX",
    # Functions from _helpers
    "_build_patient_onboarding_entry_token",
    "_localized_main_menu",
    "_localized_notification_consent_menu",
    "_localized_services_menu",
    "_localized_settings_menu",
    "_localized_text",
    "_normalize_patient_language",
    "_parse_patient_mini_app_entry_token",
    "_parse_patient_onboarding_entry_token",
    "_telegram_settings_message",
    # Functions from _clinic_bot
    "_handle_clinic_bot_update",
    # Functions from _patient_commands
    "_send_patient_bot_reply",
    # Functions from _staff_commands
    "_build_lab_report_pdf",
    "_clinic_payments_message",
    "_clinic_queue_message",
    "_clinic_visits_message",
    "_handle_contact_link",
    "_handle_staff_link_start",
    "_handle_staff_read_only_menu",
    "_handle_ticket_qr_start",
    "_latest_ready_lab_report_instances",
    "_queue_entry_position",
    "_send_clinic_lab_results",
]
