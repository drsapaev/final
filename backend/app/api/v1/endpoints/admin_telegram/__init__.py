"""
Admin Telegram package.

Re-exports router and shared helper symbols for backward compatibility.

P0-2 FIX (ENDPOINT-VALIDATION-AUDIT):
  1. Submodule imports below register their routes on the shared `router`.
     Without them, admin_telegram.router had ZERO routes and all admin
     Telegram endpoints (get_telegram_users, put_telegram_settings,
     staff actions, AI approval) were dead code.
  2. Explicit re-export of underscore-prefixed symbols (e.g.
     `_build_staff_bot_status`, `_get_configured_bot_token`) is required
     because `from ... import *` does not pick up underscore names, but
     `telegram_webhook/_helpers.py` imports them from this package path.
"""
# Import endpoint modules to register routes on the shared router.
from app.api.v1.endpoints.admin_telegram import (
    _ai_approval,  # noqa: F401
    _management,  # noqa: F401
    _settings,  # noqa: F401
    _staff_actions,  # noqa: F401
)
import requests  # noqa: F401
from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa: F401, F403

# Re-export underscore-prefixed symbols that other modules (notably
# telegram_webhook/_helpers.py) import from this package path.
from app.api.v1.endpoints.admin_telegram._helpers import (  # noqa: F401
    PATIENT_BOOKING_ENTRY_ROUTE,
    PATIENT_MINI_APP_ENTRY_ROUTE,
    PATIENT_PAYMENT_ENTRY_ROUTE,
    STAFF_BOT_COMMAND_REGISTRATION_CONTRACT,
    STAFF_BOT_CONFIRMATION_CONTRACT,
    STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS,
    STAFF_BOT_READ_ONLY_MENU_CONTRACT,
    STAFF_LINK_TOKEN_PREFIX,
    STAFF_LINK_TOKEN_SEPARATOR,
    _build_staff_bot_status,
    _normalize_staff_role,
    _staff_runtime_reference_hash,
    router,
    validate_staff_link_start_token,
)
from app.api.v1.endpoints.admin_telegram._staff_actions import (  # noqa: F401
    _get_configured_bot_token,
    _get_staff_bot_token_runtime_status,
    _staff_bot_read_only_command_payload,
    confirm_staff_action,
)
from app.api.v1.endpoints.admin_telegram._helpers import (  # noqa: F401
    _build_telegram_ai_approval_status,
    issue_staff_link_start_token,
)
from app.api.v1.endpoints.admin_telegram._settings import (  # noqa: F401
    get_telegram_settings,
    get_telegram_webhook_info,
    register_staff_bot_commands,
)
from app.api.v1.endpoints.admin_telegram._ai_approval import (  # noqa: F401
    send_telegram_ai_approval_alert,
    capture_telegram_ai_approval_outcome,
)

__all__ = [
    "router",
    "requests",
    "PATIENT_BOOKING_ENTRY_ROUTE",
    "PATIENT_MINI_APP_ENTRY_ROUTE",
    "PATIENT_PAYMENT_ENTRY_ROUTE",
    "STAFF_BOT_COMMAND_REGISTRATION_CONTRACT",
    "STAFF_BOT_CONFIRMATION_CONTRACT",
    "STAFF_BOT_READ_ONLY_DOMAIN_DATA_COMMAND_KEYS",
    "STAFF_BOT_READ_ONLY_MENU_CONTRACT",
    "STAFF_LINK_TOKEN_PREFIX",
    "STAFF_LINK_TOKEN_SEPARATOR",
    "_build_staff_bot_status",
    "_get_configured_bot_token",
    "_get_staff_bot_token_runtime_status",
    "_staff_bot_read_only_command_payload",
    "_normalize_staff_role",
    "_staff_runtime_reference_hash",
    "validate_staff_link_start_token",
    "confirm_staff_action",
    "issue_staff_link_start_token",
    "get_telegram_webhook_info",
    "get_telegram_settings",
    "register_staff_bot_commands",
    "_build_telegram_ai_approval_status",
    "send_telegram_ai_approval_alert",
    "capture_telegram_ai_approval_outcome",
]
