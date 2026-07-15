"""
Telegram webhook routes.

Split from telegram_webhook.py (5647 LOC → modular).
"""
from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.telegram_webhook._clinic_bot import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._clinic_bot import (  # noqa: F401
    _build_mini_app_appointment_booking_preview_from_request,
    _build_mini_app_patient_cabinet_summary_from_request,
    _build_mini_app_patient_forms_preview_from_request,
    _build_mini_app_patient_manifest_from_request,
    _build_mini_app_patient_report_download_response,
    _handle_clinic_bot_update,
    _raise_telegram_webhook_internal_error,
    _save_mini_app_patient_form_submission_from_request,
    _telegram_bot_info_failure,
    _telegram_user_from_onboarding_request_auth,
    _validate_webhook_secret,
)

# Import everything from all submodules (wildcard for backward compat)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403

# Specific imports
# Use the shared router from _helpers (not a new instance) so that routes
# registered here are visible when api.py imports telegram_webhook.router.
from app.api.v1.endpoints.telegram_webhook._helpers import (
    Depends,
    Request,
    Response,
    _telegram_update_summary,
    get_db,
    logger,
    router,  # noqa: F401
    status,
)
from app.api.v1.endpoints.telegram_webhook._patient_commands import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._staff_commands import *  # noqa: F401, F403
from app.schemas.notifications import (
    SendMessageRequest,
    TelegramWebhookUpdateRequest,
)


def _is_duplicate_update(db, update_id: int | None) -> bool:
    """P1-9: check if this Telegram update was already processed."""
    if update_id is None:
        return False
    try:
        from app.models.telegram_webhook_dedup import TelegramWebhookDedup
        existing = db.query(TelegramWebhookDedup).filter(
            TelegramWebhookDedup.update_id == update_id
        ).first()
        if existing:
            return True
        # Record this update_id
        dedup = TelegramWebhookDedup(update_id=update_id)
        db.add(dedup)
        db.commit()
        return False
    except Exception:
        return False  # Non-blocking: if dedup fails, process anyway

@router.post(
    "/mini-app/onboarding/requests",
    response_model=PatientOnboardingSubmitResponse,
    operation_id="telegram_mini_app_submit_patient_onboarding_request",
)
def submit_mini_app_patient_onboarding_request(
    request_body: PatientOnboardingSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit a REQUEST_REVIEW onboarding request without creating a Patient."""

    telegram_user = _telegram_user_from_onboarding_request_auth(db, request_body)
    row, created = PatientOnboardingService(db).submit(
        telegram_user=telegram_user,
        payload=request_body,
    )
    return PatientOnboardingService(db).submit_response(row, created=created)


@router.post(
    "/mini-app/onboarding/status",
    response_model=PatientOnboardingStatusResponse,
    operation_id="telegram_mini_app_read_patient_onboarding_status",
)
def read_mini_app_patient_onboarding_status(
    request_body: PatientOnboardingAuthRequest,
    db: Session = Depends(get_db),
):
    """Return the caller's own onboarding request status."""

    telegram_user = _telegram_user_from_onboarding_request_auth(db, request_body)
    return PatientOnboardingService(db).own_status_response(telegram_user)


@router.get(
    "/onboarding/requests",
    response_model=RegistrarOnboardingListResponse,
    operation_id="telegram_registrar_list_patient_onboarding_requests",
)
def list_registrar_patient_onboarding_requests(
    status_filter: str = "pending_review",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """List patient onboarding requests for registrar review."""

    allowed_statuses = {
        "pending_review",
        "linked_existing",
        "created_patient",
        "needs_more_info",
        "rejected",
        "cancelled",
        "expired",
    }
    if status_filter and status_filter not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "onboarding_status_invalid"},
        )
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return PatientOnboardingService(db).list_pending(
        status_filter=status_filter,
        limit=safe_limit,
        offset=safe_offset,
    )


@router.get(
    "/onboarding/analytics/summary",
    response_model=OnboardingAnalyticsSummaryResponse,
    operation_id="telegram_registrar_patient_onboarding_analytics_summary",
)
def get_registrar_patient_onboarding_analytics_summary(
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Return safe onboarding funnel metrics for the registrar/admin dashboard."""

    del current_user
    return PatientOnboardingService(db).analytics_summary()


@router.get(
    "/onboarding/requests/export",
    operation_id="telegram_registrar_export_patient_onboarding_requests_csv",
response_model=dict[str, Any],
)
def export_registrar_patient_onboarding_requests_csv(
    status_filter: str = "",
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Export masked onboarding requests for operational review."""

    del current_user
    csv_text = PatientOnboardingService(db).export_requests_csv(
        status_filter=status_filter
    )
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="telegram_onboarding_requests.csv"'
            )
        },
    )


@router.post(
    "/onboarding/requests/{request_id}/search-patients",
    response_model=OnboardingSearchResponse,
    operation_id="telegram_registrar_search_patient_onboarding_candidates",
)
def search_patient_candidates_for_onboarding_request(
    request_id: int,
    request_body: OnboardingPatientSearchRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Search safe duplicate candidates before linking or creating a patient."""

    return PatientOnboardingService(db).search_candidates_for_request(
        request_id=request_id,
        actor=current_user,
        search_payload=request_body,
    )


@router.post(
    "/onboarding/requests/{request_id}/link-existing",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_link_existing_patient_onboarding_request",
)
def link_existing_patient_onboarding_request(
    request_id: int,
    request_body: RegistrarPatientLinkDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Link a reviewed onboarding request to an existing patient."""

    return PatientOnboardingService(db).link_existing_patient(
        request_id=request_id,
        payload=request_body,
        actor=current_user,
    )


@router.post(
    "/onboarding/requests/{request_id}/create-patient",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_create_patient_from_onboarding_request",
)
def create_patient_from_onboarding_request(
    request: Request,
    request_id: int,
    request_body: RegistrarPatientCreateDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Create a Patient only after staff review, then link Telegram."""

    return PatientOnboardingService(db).create_patient_from_request(
        request=request,
        request_id=request_id,
        payload=request_body,
        actor=current_user,
    )


@router.post(
    "/onboarding/requests/{request_id}/request-more-info",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_request_more_info_onboarding_request",
)
def request_more_info_for_onboarding_request(
    request_id: int,
    request_body: RegistrarOnboardingReviewDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Ask the patient for more safe intake details."""

    return PatientOnboardingService(db).request_more_info(
        request_id=request_id,
        actor=current_user,
        reason_code=request_body.reason_code,
        safe_note=request_body.safe_note,
    )


@router.post(
    "/onboarding/requests/{request_id}/reject",
    response_model=RegistrarOnboardingActionResponse,
    operation_id="telegram_registrar_reject_patient_onboarding_request",
)
def reject_patient_onboarding_request(
    request_id: int,
    request_body: RegistrarOnboardingReviewDecisionRequest,
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    db: Session = Depends(get_db),
):
    """Reject an onboarding request with a safe patient-facing reason."""

    return PatientOnboardingService(db).reject(
        request_id=request_id,
        actor=current_user,
        reason_code=request_body.reason_code,
        safe_note=request_body.safe_note,
    )


# M4-P0-2: Telegram Mini App JWT Exchange endpoint.
# Replaces per-request initData-replay with short-lived JWT.
@router.post(
    "/mini-app/auth/exchange",
    operation_id="telegram_mini_app_auth_exchange",
    response_model=dict[str, Any],
)
def exchange_mini_app_auth(
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange Telegram Mini App initData for short-lived JWT.

    M4-P0-2: Secure alternative to per-request initData replay.
    - initData validated ONCE (max_age=5min, replay protection)
    - Returns JWT access_token (15 min) + refresh_token (7 days)
    - Subsequent requests should use Authorization: Bearer <access_token>

    Request body: { "init_data": "<Telegram.WebApp.initData>" }
    """
    from app.api.v1.endpoints.admin_telegram import _get_configured_bot_token
    from app.services.telegram_mini_app_jwt import (
        TelegramMiniAppAuthExchangeError,
        exchange_init_data_for_jwt,
    )

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data_payload = body.get("init_data") if isinstance(body, dict) else None
    if not init_data_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "init_data_required"},
        )

    bot_token = _get_configured_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "bot_token_required"},
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        result = exchange_init_data_for_jwt(
            db,
            init_data_payload,
            bot_token=bot_token,
            request_ip=client_ip,
            request_user_agent=user_agent,
        )
    except TelegramMiniAppAuthExchangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        ) from exc

    return result


# M4-P0-3: Patient session management endpoints.
# Allow patients to view active sessions and revoke all (e.g. if phone is stolen).
@router.post(
    "/mini-app/sessions/list",
    operation_id="telegram_mini_app_patient_sessions_list",
    response_model=dict[str, Any],
)
def list_mini_app_patient_sessions(
    request: Request,
    db: Session = Depends(get_db),
):
    """List active patient sessions (M4-P0-3).

    Returns active sessions for the authenticated patient, including
    IP, user-agent, and creation timestamp. Uses initData for auth
    (backward compat — will be replaced by JWT in future).

    Request body: { "init_data": "<Telegram.WebApp.initData>" }
    """
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
        LEGACY_MAX_AUTH_AGE_SECONDS,
    )
    from app.models.authentication import UserSession

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data") if isinstance(body, dict) else None
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "init_data_required"},
        )

    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=init_data,
            entry_token=None,
            expected_section="cabinet",
        )
    except Exception as exc:
        reason = getattr(exc, "reason", "auth_failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": reason},
        ) from exc

    # Patient sessions use negative user_id (see telegram_mini_app_jwt.py)
    patient_session_user_id = -int(scope.patient_id)
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == patient_session_user_id,
            UserSession.revoked == False,
        )
        .order_by(UserSession.created_at.desc())
        .all()
    )

    return {
        "sessions": [
            {
                "id": s.id,
                "ip": s.ip,
                "user_agent": s.user_agent,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "is_current": False,  # TODO: compare with current session's refresh_token
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.post(
    "/mini-app/sessions/revoke-all",
    operation_id="telegram_mini_app_patient_sessions_revoke_all",
    response_model=dict[str, Any],
)
def revoke_all_mini_app_patient_sessions(
    request: Request,
    db: Session = Depends(get_db),
):
    """Revoke all patient sessions except the current one (M4-P0-3).

    Used when patient suspects their phone is stolen or wants to
    log out from all other devices.

    Request body: { "init_data": "<Telegram.WebApp.initData>" }
    """
    from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
        _resolve_mini_app_patient_scope_from_auth,
    )
    from app.models.authentication import UserSession
    from datetime import UTC, datetime

    try:
        body = request.json()
    except Exception:
        body = {}

    init_data = body.get("init_data") if isinstance(body, dict) else None
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "init_data_required"},
        )

    try:
        scope, _auth_source = _resolve_mini_app_patient_scope_from_auth(
            db,
            init_data_payload=init_data,
            entry_token=None,
            expected_section="cabinet",
        )
    except Exception as exc:
        reason = getattr(exc, "reason", "auth_failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": reason},
        ) from exc

    # Revoke all patient sessions (patient sessions use negative user_id)
    patient_session_user_id = -int(scope.patient_id)
    revoked_count = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == patient_session_user_id,
            UserSession.revoked == False,
        )
        .update({"revoked": True, "revoked_at": datetime.now(UTC)})
    )
    db.commit()

    # M4-P0-1: Audit log the session revocation
    from app.services.patient_access_audit import log_patient_access
    log_patient_access(
        db=db,
        scope=scope,
        resource_type="session_management",
        action="revoke_all",
        outcome="success",
        request=request,
        extra_data={"revoked_count": revoked_count},
    )

    return {
        "revoked": True,
        "revoked_count": revoked_count,
        "message": f"Отозвано сессий: {revoked_count}",
    }


@router.post(
    "/mini-app/appointments/preview",
    operation_id="telegram_mini_app_preview_appointment_booking",
response_model=dict[str, Any],
)
def preview_mini_app_appointment_booking(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return a trusted Mini App appointment preview without creating it."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
        request=request,  # M4-P0-1: pass request for audit logging
    )
    return preview.to_response_payload()


@router.post(
    "/mini-app/forms/submissions",
    operation_id="telegram_mini_app_submit_patient_form",
response_model=dict[str, Any],
)
def submit_mini_app_patient_form(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or update one protected Mini App patient form submission."""

    result = _save_mini_app_patient_form_submission_from_request(
        request_body,
        db,
        request=request,  # M4-P0-1: pass request for audit logging
    )
    return result.to_response_payload()


@router.post(
    "/mini-app/cabinet/summary",
    operation_id="telegram_mini_app_patient_cabinet_summary",
response_model=dict[str, Any],
)
def preview_mini_app_patient_cabinet_summary(
    request_body: TelegramMiniAppPatientCabinetSummaryRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return protected patient cabinet summary without exposing Telegram ids."""

    return _build_mini_app_patient_cabinet_summary_from_request(
        request_body,
        db,
        request=request,  # M4-P0-1: pass request for audit logging
    )


@router.post(
    "/mini-app/reports/download",
    operation_id="telegram_mini_app_patient_report_download",
response_model=dict[str, Any],
)
def download_mini_app_patient_report(
    request_body: TelegramMiniAppPatientReportDownloadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return one protected ready PDF report for the linked Mini App patient."""

    return _build_mini_app_patient_report_download_response(
        request_body,
        db,
        request=request,  # M4-P0-1: pass request for audit logging
    )


@router.post(
    "/mini-app/patient/manifest",
    operation_id="telegram_mini_app_patient_manifest",
response_model=dict[str, Any],
)
def preview_mini_app_patient_manifest(
    request_body: TelegramMiniAppPatientManifestRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return safe Mini App capability manifest for a linked patient."""

    return _build_mini_app_patient_manifest_from_request(
        request_body,
        db,
        request=request,  # M4-P0-1: pass request for audit logging
    )


@router.post(
    "/mini-app/forms/preview",
    operation_id="telegram_mini_app_preview_patient_forms",
response_model=dict[str, Any],
)
def preview_mini_app_patient_forms(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return trusted Mini App patient form metadata without storing data."""

    preview = _build_mini_app_patient_forms_preview_from_request(
        request_body,
        db,
        request=request,  # M4-P0-1: pass request for audit logging
    )
    return preview.to_response_payload()


@router.post(
    "/mini-app/appointments",
    status_code=status.HTTP_201_CREATED,
    operation_id="telegram_mini_app_create_appointment_booking",
response_model=dict[str, Any],
)
def create_mini_app_appointment_booking(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create one trusted Mini App appointment for a linked patient."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
        request=request,  # M4-P0-1: pass request for audit logging
    )
    draft_payload = preview.draft.to_appointment_create_payload()

    if preview.draft.doctor_id is not None and preview.draft.appointment_time:
        slot_occupied = appointment_crud.is_time_slot_occupied(
            db,
            doctor_id=preview.draft.doctor_id,
            appointment_date=preview.draft.appointment_date,
            appointment_time=preview.draft.appointment_time,
        )
        if slot_occupied:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "appointment_time_slot_occupied"},
            )

    appointment_create_payload = dict(draft_payload)
    appointment_create_payload.pop("department", None)
    appointment_in = appointment_schemas.AppointmentCreate(**appointment_create_payload)
    appointment = appointment_crud.create(db=db, obj_in=appointment_in)

    # M4-P0-1: PHI audit trail — log appointment creation
    from app.services.patient_access_audit import log_patient_access
    log_patient_access(
        db=db,
        scope=preview.scope,
        resource_type="appointment",
        resource_id=str(appointment.id),
        action="create",
        outcome="success",
        request=request,
        extra_data={
            "appointment_date": str(preview.draft.appointment_date),
            "appointment_time": preview.draft.appointment_time,
            "department": preview.draft.department,
        },
    )

    return {
        "created": True,
        "appointment_id": int(appointment.id),
        "preview": preview.to_response_payload(),
    }


@router.post("/webhook", response_model=dict[str, Any])
async def telegram_webhook(
    body: TelegramWebhookUpdateRequest, request: Request, db: Session = Depends(get_db)
):
    """
    Webhook endpoint для получения обновлений от Telegram
    """
    try:
        _validate_webhook_secret(request, db)
        update = body.model_dump(exclude_none=True)
        logger.info(
            "Telegram webhook update accepted",
            extra=_telegram_update_summary(update),
        )

        # Получаем сервис бота
        # Resolve via package namespace so monkeypatch of
        # telegram_webhook.get_telegram_bot_service takes effect.
        from app.api.v1.endpoints.telegram_webhook import (
            get_telegram_bot_service as _get_telegram_bot_service,
        )
        bot_service = await _get_telegram_bot_service()

        # Инициализируем бота если нужно
        if not bot_service.active:
            await bot_service.initialize(db)

        # Обрабатываем обновление
        if await _handle_clinic_bot_update(update, db, bot_service):
            return {"status": "ok", "handled": "clinic_bot_update"}

        # If _handle_clinic_bot_update returned False, the update was not
        # handled by any clinic bot handler. Try the legacy
        # process_webhook_update method as a fallback.
        process_wh = getattr(bot_service, "process_webhook_update", None)
        if callable(process_wh):
            await process_wh(update, db)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "telegram_webhook",
            TELEGRAM_WEBHOOK_PUBLIC_ERROR,
            e,
        )


@router.get("/webhook", response_model=dict[str, Any])
async def verify_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Проверка webhook (для верификации)
    """
    try:
        # Telegram может отправлять GET запросы для проверки webhook
        return {"status": "webhook_verified"}

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "verify_webhook",
            "Ошибка проверки webhook",
            e,
        )


@router.post("/send-message", response_model=dict[str, Any])
async def send_message_to_user(
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    body: SendMessageRequest = SendMessageRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Отправка сообщения пользователю через бота.

    P0-6e FIX: removed the redundant ``reply_markup: dict[str, Any] | None``
    keyword argument. The ``body: SendMessageRequest`` model is now the
    single source of truth for ``reply_markup`` — Pydantic caps the
    dict at 50 keys via ``SendMessageRequest._validate_reply_markup_size``.
    Direct callers (e.g. unit tests) should pass ``body=SendMessageRequest(reply_markup=...)``
    instead of ``reply_markup=...``.
    """
    try:
        # Resolve ``get_telegram_bot_service`` via the package attribute at
        # call time. Unit tests monkeypatch ``telegram_webhook.get_telegram_bot_service``
        # (the package-level binding); looking the function up via the local
        # module import would bypass that patch.
        from app.api.v1.endpoints.telegram_webhook import (
            get_telegram_bot_service as _get_telegram_bot_service,
        )
        bot_service = await _get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        effective_reply_markup = body.reply_markup
        success = await bot_service._send_message(
            chat_id=chat_id, text=message, reply_markup=effective_reply_markup
        )

        if success:
            return {"status": "sent"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка отправки сообщения",
            )

    except HTTPException:
        raise
    except Exception as e:
        _raise_telegram_webhook_internal_error(
            "send_message_to_user",
            TELEGRAM_SEND_PUBLIC_ERROR,
            e,
        )


@router.get("/bot-info", operation_id="telegram_webhook_get_bot_info", response_model=dict[str, Any])
async def get_bot_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить информацию о боте
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        if not bot_service.bot_token:
            return {"active": False, "message": "Бот не настроен"}

        # Получаем информацию о боте через API
        import httpx

        response = httpx.get(
            f"https://api.telegram.org/bot{bot_service.bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_data = response.json()
            if bot_data.get("ok"):
                return {
                    "active": True,
                    "bot_info": bot_data["result"],
                    "webhook_url": bot_service.webhook_url,
                }

        return {"active": False, "message": "Ошибка получения информации о боте"}

    except HTTPException:
        raise
    except Exception as e:
        return _telegram_bot_info_failure(e)
