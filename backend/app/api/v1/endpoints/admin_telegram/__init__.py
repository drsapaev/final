"""
Admin Telegram package.

Re-exports everything from all submodules for backward compatibility.
"""
from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_telegram._staff_actions import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_telegram._ai_approval import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_telegram._settings import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_telegram._management import *  # noqa: F401, F403

# Explicitly re-export private names (import * skips underscore-prefixed)
from app.api.v1.endpoints.admin_telegram._helpers import (  # noqa: F401
    _base36_encode, _base36_decode,
    _staff_link_token_expires_epoch, _staff_link_token_signature,
    _hash_staff_link_start_token, _decode_staff_link_start_token,
    _build_staff_role_menus_summary, _build_staff_role_menu_enablement_contract,
    _build_staff_bot_next_slice,
    _staff_runtime_reference_hash, _telegram_ai_approval_reference_hash,
    _telegram_ai_approval_workflow, _protected_frontend_url,
    _safe_ai_approval_value, _safe_ai_approval_metrics,
    _build_telegram_ai_approval_status, _assert_ai_approval_role_allowed,
    _normalize_ai_approval_outcome, _normalize_ai_approval_reason_code,
    _staff_state_change_operation_by_key,
    _build_staff_bot_status,
    _normalize_staff_role,
    _record_staff_action_execution_failure,
    _validate_staff_action_target_request,
    _staff_action_expected_target_binding,
    _validate_staff_action_target_binding,
)
from app.api.v1.endpoints.admin_telegram._staff_actions import (  # noqa: F401
    _get_configured_bot_token,
    _get_staff_bot_token_runtime_status,
    _sanitize_telegram_webhook_info,
    _has_secret_value,
    _build_staff_bot_token_status,
    _get_configured_staff_bot_token,
    _build_staff_bot_token_contract,
    _staff_bot_read_only_command_payload,
    _build_staff_command_registration_contract,
    _get_configured_bot_username,
    _fetch_telegram_webhook_info,
    raise_admin_telegram_error,
    webhook_info_error_response,
)

__all__ = ["router"]
