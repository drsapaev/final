"""
Telegram webhook routes.

Split from telegram_webhook.py (5647 LOC → modular).
"""
from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.telegram_webhook._clinic_bot import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._clinic_bot import (
    _handle_clinic_bot_update,
    _raise_telegram_webhook_internal_error,
    _validate_webhook_secret,
)

# Import everything from all submodules (wildcard for backward compat)
from app.api.v1.endpoints.telegram_webhook._helpers import *  # noqa: F401, F403

# Specific imports
from app.api.v1.endpoints.telegram_webhook._helpers import (
    APIRouter,
    Depends,
    Request,
    Response,
    get_db,
    logger,
    status,
)
from app.api.v1.endpoints.telegram_webhook._patient_commands import *  # noqa: F401, F403
from app.api.v1.endpoints.telegram_webhook._staff_commands import *  # noqa: F401, F403
from app.schemas.notifications import (
    SendMessageRequest,
    TelegramWebhookUpdateRequest,
)

router = APIRouter()


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


@router.post(
    "/mini-app/appointments/preview",
    operation_id="telegram_mini_app_preview_appointment_booking",
response_model=dict[str, Any],
)
def preview_mini_app_appointment_booking(
    request_body: TelegramMiniAppAppointmentPreviewRequest,
    db: Session = Depends(get_db),
):
    """Return a trusted Mini App appointment preview without creating it."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
    )
    return preview.to_response_payload()


@router.post(
    "/mini-app/forms/submissions",
    operation_id="telegram_mini_app_submit_patient_form",
response_model=dict[str, Any],
)
def submit_mini_app_patient_form(
    request_body: TelegramMiniAppPatientFormSubmissionRequest,
    db: Session = Depends(get_db),
):
    """Create or update one protected Mini App patient form submission."""

    result = _save_mini_app_patient_form_submission_from_request(
        request_body,
        db,
    )
    return result.to_response_payload()


@router.post(
    "/mini-app/cabinet/summary",
    operation_id="telegram_mini_app_patient_cabinet_summary",
response_model=dict[str, Any],
)
def preview_mini_app_patient_cabinet_summary(
    request_body: TelegramMiniAppPatientCabinetSummaryRequest,
    db: Session = Depends(get_db),
):
    """Return protected patient cabinet summary without exposing Telegram ids."""

    return _build_mini_app_patient_cabinet_summary_from_request(
        request_body,
        db,
    )


@router.post(
    "/mini-app/reports/download",
    operation_id="telegram_mini_app_patient_report_download",
response_model=dict[str, Any],
)
def download_mini_app_patient_report(
    request_body: TelegramMiniAppPatientReportDownloadRequest,
    db: Session = Depends(get_db),
):
    """Return one protected ready PDF report for the linked Mini App patient."""

    return _build_mini_app_patient_report_download_response(request_body, db)


@router.post(
    "/mini-app/patient/manifest",
    operation_id="telegram_mini_app_patient_manifest",
response_model=dict[str, Any],
)
def preview_mini_app_patient_manifest(
    request_body: TelegramMiniAppPatientManifestRequest,
    db: Session = Depends(get_db),
):
    """Return safe Mini App capability manifest for a linked patient."""

    return _build_mini_app_patient_manifest_from_request(request_body, db)


@router.post(
    "/mini-app/forms/preview",
    operation_id="telegram_mini_app_preview_patient_forms",
response_model=dict[str, Any],
)
def preview_mini_app_patient_forms(
    request_body: TelegramMiniAppPatientFormsPreviewRequest,
    db: Session = Depends(get_db),
):
    """Return trusted Mini App patient form metadata without storing data."""

    preview = _build_mini_app_patient_forms_preview_from_request(
        request_body,
        db,
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
    db: Session = Depends(get_db),
):
    """Create one trusted Mini App appointment for a linked patient."""

    preview = _build_mini_app_appointment_booking_preview_from_request(
        request_body,
        db,
        allow_entry_token=True,
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
        bot_service = await get_telegram_bot_service()

        # Инициализируем бота если нужно
        if not bot_service.active:
            await bot_service.initialize(db)

        # Обрабатываем обновление
        if await _handle_clinic_bot_update(update, db, bot_service):
            return {"status": "ok", "handled": "clinic_bot_update"}

        await bot_service.process_webhook_update(update, db)

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
    Отправка сообщения пользователю через бота
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        success = await bot_service._send_message(
            chat_id=chat_id, text=message, reply_markup=body.reply_markup
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
