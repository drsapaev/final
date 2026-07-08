from __future__ import annotations

from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa


@router.post("/telegram/staff-actions/{confirmation_id}/confirm", response_model=dict[str, Any])
def confirm_staff_action(
    confirmation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Owner",
            "Doctor",
            "Lab",
            "admin",
            "registrar",
            "cashier",
            "owner",
            "doctor",
            "lab",
        )
    ),
    request: StaffActionConfirmRequest | None = Body(default=None),
) -> dict[str, Any]:
    """Confirm one explicitly enabled Telegram staff action in the protected app."""

    if not isinstance(request, StaffActionConfirmRequest):
        request = StaffActionConfirmRequest()
    record = (
        db.query(TelegramStaffConfirmationToken)
        .filter(TelegramStaffConfirmationToken.id == confirmation_id)
        .first()
    )
    if not record or int(record.staff_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff action confirmation not found",
        )

    operation_key = str(record.operation_key or "")
    command_key = str(record.command_key or "")
    operation = _staff_state_change_operation_by_key(operation_key)
    if not operation:
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason="operation_not_registered",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff action operation is not registered",
        )

    role = _normalize_staff_role(getattr(current_user, "role", None))
    allowed_roles = {
        _normalize_staff_role(role_key) for role_key in operation.get("roles", [])
    }
    if role not in allowed_roles:
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason="role_not_allowed",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current role cannot confirm this staff action",
        )

    enabled_commands = {
        str(item).strip().lower()
        for item in STAFF_BOT_ACTION_ENABLEMENT_CONTRACT.get("enabled_commands", [])
    }
    if command_key.lower() not in enabled_commands:
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason="command_not_enabled",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff action command is not enabled for protected execution",
        )

    target_error = _validate_staff_action_target_request(command_key, request)
    if target_error:
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason=target_error,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=target_error,
        )

    target_binding_error = _validate_staff_action_target_binding(
        record,
        command_key,
        request,
    )
    if target_binding_error:
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason=target_binding_error,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=target_binding_error,
        )

    consume_result = TelegramStaffConfirmationTokenService(db).consume_for_confirmation(
        token_hash=record.token_hash,
        staff_user_id=int(current_user.id),
        telegram_chat_id=int(record.telegram_chat_id),
        operation_key=record.operation_key,
        action_payload_hash=record.action_payload_hash,
        idempotency_key_hash=record.idempotency_key_hash,
    )
    if not consume_result.get("valid"):
        _record_staff_action_execution_failure(
            db,
            record=record,
            current_user=current_user,
            operation_key=operation_key,
            command_key=command_key,
            reason=str(consume_result.get("reason") or "confirmation_rejected"),
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": consume_result.get("reason") or "confirmation_rejected",
                "single_use_enforced": bool(
                    consume_result.get("single_use_enforced")
                ),
            },
        )

    if command_key.lower() == "/call":
        action_result = TelegramStaffActionAdapterService(db).staff_call_next_patient(
            actor_user_id=int(current_user.id),
            telegram_chat_id=int(record.telegram_chat_id),
            commit=True,
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "status": action_result.get("status"),
            "queue_time_preserved": action_result.get("queue_time_preserved"),
        }

    if command_key.lower() == "/skip":
        action_result = TelegramStaffActionAdapterService(db).staff_skip_queue_entry(
            entry_id=int(request.entry_id),
            actor_user_id=int(current_user.id),
            telegram_chat_id=int(record.telegram_chat_id),
            commit=True,
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "status": action_result.get("status"),
            "queue_time_preserved": action_result.get("queue_time_preserved"),
        }

    if command_key.lower() == "/cancel_visit":
        action_result = TelegramStaffActionAdapterService(db).staff_cancel_visit(
            visit_id=int(request.visit_id),
            actor_user_id=int(current_user.id),
            telegram_chat_id=int(record.telegram_chat_id),
            commit=True,
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "visit_status": action_result.get("visit_status"),
        }

    if command_key.lower() == "/move_visit":
        action_result = TelegramStaffActionAdapterService(db).staff_move_visit(
            visit_id=int(request.visit_id),
            new_visit_date=request.new_visit_date,
            actor_user_id=int(current_user.id),
            telegram_chat_id=int(record.telegram_chat_id),
            commit=True,
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "visit_date": action_result.get("visit_date").isoformat()
            if action_result.get("visit_date")
            else None,
        }

    if command_key.lower() == "/payment_status":
        action_result = (
            TelegramStaffActionAdapterService(db).staff_change_payment_status(
                payment_id=int(request.payment_id),
                new_status=str(request.new_status),
                actor_user_id=int(current_user.id),
                telegram_chat_id=int(record.telegram_chat_id),
                commit=True,
            )
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "status": action_result.get("status"),
        }

    if command_key.lower() == "/refund":
        action_result = TelegramStaffActionAdapterService(db).staff_refund_payment(
            payment_id=int(request.payment_id),
            amount=request.refund_amount,
            reason=request.refund_reason,
            actor_user_id=int(current_user.id),
            telegram_chat_id=int(record.telegram_chat_id),
            commit=True,
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "status": action_result.get("status"),
        }

    if command_key.lower() == "/change_schedule":
        action_result = (
            TelegramStaffActionAdapterService(db).staff_change_doctor_schedule(
                schedule_id=int(request.schedule_id),
                start_time=request.start_time,
                end_time=request.end_time,
                breaks=request.breaks,
                active=request.active,
                actor_user_id=int(current_user.id),
                telegram_chat_id=int(record.telegram_chat_id),
                commit=True,
            )
        )
        return {
            "success": True,
            "confirmation_id": confirmation_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "action": action_result.get("action"),
            "active": action_result.get("active"),
        }

    _record_staff_action_execution_failure(
        db,
        record=record,
        current_user=current_user,
        operation_key=operation_key,
        command_key=command_key,
        reason="enabled_command_missing_executor",
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Enabled staff action has no executor",
    )


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
) -> dict[str, Any]:
    logger.warning(
        "Admin Telegram webhook info failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    return {"webhook_set": False, "error": public_error}


def _sanitize_telegram_webhook_info(webhook_info: dict[str, Any]) -> dict[str, Any]:
    pending_update_count = webhook_info.get("pending_update_count")
    if isinstance(pending_update_count, bool) or not isinstance(
        pending_update_count, int
    ):
        pending_update_count = 0

    return {
        "url": str(webhook_info.get("url") or ""),
        "pending_update_count": pending_update_count,
    }


class TelegramWebhookRequest(BaseModel):
    webhook_url: str | None = None


def _has_secret_value(value: Any) -> bool:
    return bool(str(value or "").strip())


def _get_configured_bot_token(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_token:
        return config.bot_token

    bot_token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
    return getattr(bot_token_setting, "value", None) if bot_token_setting else None


def _build_staff_bot_token_status(
    *,
    token_value: Any,
    source: str,
    source_key: str,
    patient_bot_token: str | None,
) -> dict[str, Any]:
    token_text = str(token_value or "").strip()
    patient_token_text = str(patient_bot_token or "").strip()
    token_present = bool(token_text)
    patient_bot_token_reused = bool(
        token_present and patient_token_text and token_text == patient_token_text
    )
    ready = token_present and not patient_bot_token_reused
    return {
        "configured": token_present,
        "ready": ready,
        "source": source,
        "source_key": source_key,
        "separate_staff_bot_token_configured": ready,
        "patient_bot_token_reused": patient_bot_token_reused,
    }


def _get_staff_bot_token_runtime_status(
    db: Session, patient_bot_token: str | None = None
) -> dict[str, Any]:
    for env_key in STAFF_BOT_TOKEN_ENV_KEYS:
        token_value = os.getenv(env_key)
        if _has_secret_value(token_value):
            return _build_staff_bot_token_status(
                token_value=token_value,
                source="environment",
                source_key=env_key,
                patient_bot_token=patient_bot_token,
            )

    for setting_key in STAFF_BOT_TOKEN_SETTING_KEYS:
        setting = crud_clinic.get_setting_by_key(db, setting_key)
        token_value = getattr(setting, "value", None)
        if _has_secret_value(token_value):
            return _build_staff_bot_token_status(
                token_value=token_value,
                source="clinic_settings",
                source_key=setting_key,
                patient_bot_token=patient_bot_token,
            )

    return {
        "configured": False,
        "ready": False,
        "source": "not_configured",
        "source_key": None,
        "separate_staff_bot_token_configured": False,
        "patient_bot_token_reused": False,
    }


def _get_configured_staff_bot_token(
    db: Session, patient_bot_token: str | None = None
) -> str | None:
    patient_token_text = str(patient_bot_token or "").strip()
    for env_key in STAFF_BOT_TOKEN_ENV_KEYS:
        token_text = str(os.getenv(env_key) or "").strip()
        if token_text and token_text != patient_token_text:
            return token_text

    for setting_key in STAFF_BOT_TOKEN_SETTING_KEYS:
        setting = crud_clinic.get_setting_by_key(db, setting_key)
        token_text = str(getattr(setting, "value", None) or "").strip()
        if token_text and token_text != patient_token_text:
            return token_text

    return None


def _build_staff_bot_token_contract(token_status: dict[str, Any]) -> dict[str, Any]:
    configured = bool(token_status.get("configured"))
    ready = bool(token_status.get("ready"))
    blocked_by = []
    if not configured:
        blocked_by.append("dedicated_staff_bot_token")
    elif not ready:
        blocked_by.append("separate_staff_bot_token_configured")
    return {
        **STAFF_BOT_TOKEN_CONTRACT,
        "enabled": ready,
        "runtime_read_enabled": True,
        "configured": configured,
        "ready": ready,
        "separate_staff_bot_token_configured": ready,
        "token_returned_to_frontend": False,
        "patient_bot_token_reused": bool(token_status.get("patient_bot_token_reused")),
        "patient_bot_transport_unchanged": True,
        "source": token_status.get("source") or "not_configured",
        "source_key": token_status.get("source_key"),
        "accepted_env_keys": list(STAFF_BOT_TOKEN_ENV_KEYS),
        "accepted_setting_keys": list(STAFF_BOT_TOKEN_SETTING_KEYS),
        "runtime_blocked_by": blocked_by,
        "checks": [
            {
                "key": "dedicated_staff_bot_token",
                "ready": configured,
            },
            {
                "key": "separate_staff_bot_token_configured",
                "ready": ready,
            },
            {
                "key": "token_not_returned_to_frontend",
                "ready": True,
            },
            {
                "key": "patient_bot_transport_unchanged",
                "ready": True,
            },
        ],
    }


def _staff_bot_read_only_command_payload() -> list[dict[str, str]]:
    commands = []
    for item in STAFF_BOT_COMMAND_REGISTRATION_CONTRACT.get("commands", []):
        if item.get("intent") != "read_only":
            continue
        command = str(item.get("command") or "").strip().lstrip("/")
        description = str(item.get("label") or command).strip()
        if command:
            commands.append(
                {
                    "command": command,
                    "description": description[:256],
                }
            )
    return commands


def _build_staff_command_registration_contract(
    token_contract: dict[str, Any],
) -> dict[str, Any]:
    token_ready = bool(token_contract.get("ready"))
    return {
        **STAFF_BOT_COMMAND_REGISTRATION_CONTRACT,
        "registration_enabled": token_ready,
        "runtime_registration_enabled": True,
        "registration_endpoint_published": True,
        "read_only_command_registration_available": token_ready,
        "read_only_commands_registered": False,
        "registered_command_scope": "read_only_staff_commands_only",
        "patient_bot_token_allowed": False,
        "state_changing_commands_registered": False,
        "runtime_blocked_by": (
            [] if token_ready else list(token_contract["runtime_blocked_by"])
        ),
        "telegram_payload_commands": _staff_bot_read_only_command_payload(),
    }


def _get_configured_bot_username(db: Session) -> str | None:
    config = crud_telegram.get_telegram_config(db)
    if config and config.bot_username:
        return config.bot_username

    bot_username_setting = crud_clinic.get_setting_by_key(db, "bot_username")
    return (
        getattr(bot_username_setting, "value", None) if bot_username_setting else None
    )


def _fetch_telegram_webhook_info(bot_token: str) -> dict[str, Any]:
    response = httpx.get(
        f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or "Telegram API error")
    return result["result"]

# ===================== НАСТРОЙКИ TELEGRAM =====================

