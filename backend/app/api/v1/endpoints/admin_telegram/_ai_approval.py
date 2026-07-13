from __future__ import annotations

from app.api.v1.endpoints.admin_telegram._helpers import *  # noqa
from app.api.v1.endpoints.admin_telegram._helpers import (
    _assert_ai_approval_role_allowed,
    _normalize_ai_approval_outcome,
    _normalize_ai_approval_reason_code,
    _normalize_staff_role,
    _protected_frontend_url,
    _staff_runtime_reference_hash,
    _telegram_ai_approval_reference_hash,
    _telegram_ai_approval_workflow,
)  # noqa: F401


@router.post("/telegram/ai-approval-alerts", response_model=dict[str, Any])
async def send_telegram_ai_approval_alert(
    request: TelegramAiApprovalAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Owner",
            "Doctor",
            "admin",
            "registrar",
            "cashier",
            "owner",
            "doctor",
        )
    ),
) -> dict[str, Any]:
    """Send one safe AI approval alert to a linked staff Telegram chat."""

    workflow_key = str(request.workflow_key or "").strip().lower()
    workflow = _telegram_ai_approval_workflow(workflow_key)
    recipient_user = db.query(User).filter(User.id == request.recipient_user_id).first()
    if not recipient_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ai_approval_recipient_not_found",
        )
    _assert_ai_approval_role_allowed(
        workflow,
        getattr(recipient_user, "role", None),
        role_field="recipient_roles",
    )

    telegram_user = crud_telegram.get_telegram_user_by_linked_user_id(
        db, request.recipient_user_id
    )
    if (
        not telegram_user
        or not bool(getattr(telegram_user, "active", False))
        or bool(getattr(telegram_user, "blocked", False))
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="linked_staff_telegram_chat_not_found",
        )

    protected_url = _protected_frontend_url(str(workflow["protected_route"]))
    if not protected_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="protected_frontend_url_not_configured",
        )

    message = build_telegram_ai_approval_message(
        workflow_key,
        protected_url,
        request.metrics,
    )
    # Resolve via package namespace so monkeypatch of
    # admin_telegram.get_telegram_bot_service takes effect.
    from app.api.v1.endpoints.admin_telegram import (
        get_telegram_bot_service as _get_telegram_bot_service,
    )
    bot_service = await _get_telegram_bot_service()
    if not bool(getattr(bot_service, "active", False)):
        await bot_service.initialize(db)
    if not getattr(bot_service, "bot_token", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram_bot_token_not_configured",
        )

    success = bool(
        await bot_service._send_message(
            int(telegram_user.chat_id),
            message["text"],
            message["reply_markup"],
        )
    )
    target_reference_hash = (
        _telegram_ai_approval_reference_hash(request.target_reference)
        if request.target_reference
        else None
    )
    crud_audit.log(
        db,
        action=(
            "telegram_ai_approval_notification_sent"
            if success
            else "telegram_ai_approval_notification_failed"
        ),
        entity_type="telegram_ai_approval",
        entity_id=None,
        actor_user_id=current_user.id,
        payload={
            "workflow_key": workflow_key,
            "notification_type": workflow["notification_type"],
            "recipient_user_id": request.recipient_user_id,
            "recipient_role": _normalize_staff_role(getattr(recipient_user, "role", None)),
            "target_reference_hash": target_reference_hash,
            "safe_metric_keys": message["safe_metric_keys"],
            "telegram_user_id_hash": _staff_runtime_reference_hash(
                "telegram_chat", telegram_user.chat_id
            ),
            "plain_chat_medical_content_allowed": False,
            "contains_plain_chat_medical_content": False,
            "autonomous_mutation_allowed": False,
            "domain_mutation": False,
            "requires_human_confirmation": True,
            "protected_route": workflow["protected_route"],
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    db.commit()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="telegram_ai_approval_notification_send_failed",
        )

    return {
        "success": True,
        "workflow_key": workflow_key,
        "recipient_user_id": request.recipient_user_id,
        "protected_route": workflow["protected_route"],
        "safe_metric_keys": message["safe_metric_keys"],
        "plain_chat_medical_content_allowed": False,
        "autonomous_mutation_allowed": False,
    }


@router.post("/telegram/ai-approval-outcomes", response_model=dict[str, Any])
def capture_telegram_ai_approval_outcome(
    request: TelegramAiApprovalOutcomeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Owner",
            "Doctor",
            "admin",
            "registrar",
            "cashier",
            "owner",
            "doctor",
        )
    ),
) -> dict[str, Any]:
    """Capture human accepted/rejected feedback without mutating domain state."""

    workflow_key = str(request.workflow_key or "").strip().lower()
    workflow = _telegram_ai_approval_workflow(workflow_key)
    _assert_ai_approval_role_allowed(
        workflow,
        getattr(current_user, "role", None),
        role_field="outcome_roles",
    )
    outcome = _normalize_ai_approval_outcome(request.outcome)
    reason_code = _normalize_ai_approval_reason_code(request.reason_code)
    target_reference_hash = (
        _telegram_ai_approval_reference_hash(request.target_reference)
        if request.target_reference
        else None
    )

    crud_audit.log(
        db,
        action="telegram_ai_approval_outcome_recorded",
        entity_type="telegram_ai_approval",
        entity_id=None,
        actor_user_id=current_user.id,
        payload={
            "workflow_key": workflow_key,
            "notification_type": workflow["notification_type"],
            "outcome": outcome,
            "reason_code": reason_code,
            "actor_role": _normalize_staff_role(getattr(current_user, "role", None)),
            "target_reference_hash": target_reference_hash,
            "plain_chat_medical_content_allowed": False,
            "contains_plain_chat_medical_content": False,
            "autonomous_mutation_allowed": False,
            "domain_mutation": False,
            "requires_human_confirmation": True,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    db.commit()

    return {
        "success": True,
        "workflow_key": workflow_key,
        "outcome": outcome,
        "reason_code": reason_code,
        "target_reference_hash": target_reference_hash,
        "plain_chat_medical_content_allowed": False,
        "autonomous_mutation_allowed": False,
        "domain_mutation": False,
    }

