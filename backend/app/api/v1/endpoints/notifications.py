import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_active_roles, require_roles
from app.core.i18n import t  # noqa: F401
from app.crud import patient as patient_crud
from app.crud import visit as visit_crud
from app.crud.notification import TemplateConcurrentUpdate, crud_notification_template
from app.crud.user_management import (
    user_notification_settings as crud_user_notification_settings,
)
from app.crud.user_management import (
    user_profile as crud_user_profile,
)
from app.models.clinic import Doctor
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.user_profile import UserPreferences
from app.models.visit import Visit
from app.schemas.notification import (
    BulkNotificationRequest,
    NotificationInboxResponse,
    NotificationMutationResponse,
    NotificationStatsResponse,
    NotificationTemplate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationUnreadCountResponse,
    SendNotificationRequest,
)
from app.schemas.notifications import (
    SendSystemAlertRequest,
    UpdateNotificationPolicyRequest,
)
from app.schemas.user_management import (
    UserNotificationSettingsCreate,
    UserNotificationSettingsResponse,
    UserNotificationSettingsUpdate,
)
from app.services.notification_platform_service import get_notification_platform_service
from app.services.notification_subject_intent_service import (
    create_patient_notification_intent,
    dispatch_patient_notification_intent,
)
from app.services.notifications import notification_sender_service
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_profile_bearer,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_TIME_PATTERN = re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")


class _InvitationReadRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            headers = {"Cache-Control": "private, no-store"}
            try:
                result = await original(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Некорректный запрос"}, headers=headers)
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
            result.headers.update(headers)
            return result

        return handler


_invitation_read_router = APIRouter(route_class=_InvitationReadRoute)


class VisitInvitationTaskResponse(BaseModel):
    visit_id: int
    patient_name: str
    patient_phone: str | None
    visit_date: str
    visit_time: str | None


class VisitInvitationStatusResponse(BaseModel):
    visit_id: int
    state: Literal["none", "pending", "unknown", "sent", "cancelled", "reissue_required"]
    channel: Literal["telegram", "pwa", "phone"] | None
    confirmation_expired: bool


@_invitation_read_router.get("/visit-invitation-status/{visit_id}", response_model=VisitInvitationStatusResponse)
def read_visit_invitation_status(
    visit_id: int, request: Request, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
):
    """Reveal only the current subject's delivery outcome to an active Admin."""
    from app.api.v1.endpoints.visit_confirmation import (
        _locked_reissue_subject,
        _reissue_audit,
    )
    from app.models.doctor_price_override import DoctorPriceOverride
    from app.models.visit_invitation_delivery import (
        VisitInvitationApprovalRecovery,
        VisitInvitationDelivery,
    )
    from app.services.visit_invitation_delivery import (
        InvitationRuntimeUnavailable,
        _digest,
        _valid_visit,
        pin_invitation_runtime,
    )

    response.headers["Cache-Control"] = "private, no-store"
    try:
        pin_invitation_runtime(db)
        bearer = capture_profile_bearer(request, current_user)
        actor, patient, visit = _locked_reissue_subject(db, visit_id, bearer)
        now = datetime.now(UTC)
        expires = visit.confirmation_expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        rows = []
        if visit.confirmation_token:
            rows = (db.query(VisitInvitationDelivery)
                    .filter(VisitInvitationDelivery.visit_id == visit.id,
                            VisitInvitationDelivery.visit_id_snapshot == visit.id,
                            VisitInvitationDelivery.patient_id == patient.id,
                            VisitInvitationDelivery.patient_id_snapshot == patient.id,
                            VisitInvitationDelivery.owner_generation == patient.notification_owner_generation,
                            VisitInvitationDelivery.context_epoch == visit.confirmation_context_epoch,
                            VisitInvitationDelivery.token_digest == _digest(visit.confirmation_token))
                    .order_by(VisitInvitationDelivery.id.desc()).limit(2).all())
        if len(rows) > 1:
            raise HTTPException(status_code=409, detail="Требуется проверка состояния")
        row = rows[0] if rows else None
        recoveries = []
        if visit.status == "pending_confirmation" and not _valid_visit(visit, patient):
            recoveries = (db.query(VisitInvitationApprovalRecovery)
                .join(DoctorPriceOverride, DoctorPriceOverride.id == VisitInvitationApprovalRecovery.override_id)
                .filter(VisitInvitationApprovalRecovery.visit_id == visit.id,
                        VisitInvitationApprovalRecovery.visit_id_snapshot == visit.id,
                        VisitInvitationApprovalRecovery.patient_id == patient.id,
                        VisitInvitationApprovalRecovery.patient_id_snapshot == patient.id,
                        VisitInvitationApprovalRecovery.owner_generation == patient.notification_owner_generation,
                        VisitInvitationApprovalRecovery.context_epoch == visit.confirmation_context_epoch,
                        VisitInvitationApprovalRecovery.previous_token_digest == (_digest(visit.confirmation_token) if visit.confirmation_token else None),
                        VisitInvitationApprovalRecovery.state.in_(["pending", "dispatched"]),
                        DoctorPriceOverride.status == "approved", DoctorPriceOverride.visit_id == visit.id,
                        DoctorPriceOverride.approved_by == VisitInvitationApprovalRecovery.actor_user_id_snapshot)
                .order_by(VisitInvitationApprovalRecovery.id.desc()).limit(2).all())
        if len(recoveries) > 1:
            raise HTTPException(status_code=409, detail="Требуется проверка состояния")
        result = VisitInvitationStatusResponse(
            visit_id=visit.id, state="reissue_required" if recoveries else (row.state if row else "none"),
            channel=None if recoveries else (row.channel if row else None),
            confirmation_expired=expires is None or expires <= now,
        )
        _reissue_audit(db, actor, visit.id, "visit_invitation_status_viewed")
        check_profile_bearer(db, actor, bearer)
        check_bearer_expiry(bearer)
        db.commit()
        return result
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен", headers={"Cache-Control": "private, no-store"}) from None
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Состояние временно недоступно", headers={"Cache-Control": "private, no-store"}) from None
    except HTTPException as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers={"Cache-Control": "private, no-store"}) from None


@_invitation_read_router.get("/visit-invitation-tasks/{handle}", response_model=VisitInvitationTaskResponse)
def read_visit_invitation_task(
    handle: str, request: Request, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin", "Registrar")),
):
    """Resolve a neutral inbox handle only for its current authorized recipient."""
    import hmac
    from uuid import UUID

    from app.models.notification import NotificationDelivery, NotificationEvent
    from app.models.visit_invitation_delivery import VisitInvitationDelivery
    from app.services.patient_access_audit import _build_patient_access_entry
    from app.services.visit_invitation_delivery import (
        InvitationRuntimeUnavailable,
        _digest,
        _lock_invitation_patient,
        _valid_visit,
        pin_invitation_runtime,
    )

    response.headers["Cache-Control"] = "private, no-store"
    missing = HTTPException(status_code=404, detail="Задача недоступна", headers={"Cache-Control": "private, no-store"})
    try:
        if str(UUID(handle)) != handle:
            raise missing
        pin_invitation_runtime(db)
        bearer = capture_profile_bearer(request, current_user)
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Задача временно недоступна", headers={"Cache-Control": "private, no-store"}) from None
    except (ValueError, ProfileBearerInvalid):
        raise missing from None
    actor = db.query(User).filter(User.id == bearer.user_id).populate_existing().with_for_update().first()
    try:
        if actor is None:
            raise ProfileBearerInvalid("Actor unavailable")
        check_profile_bearer(db, actor, bearer)
    except ProfileBearerInvalid:
        db.rollback()
        raise missing from None
    if (actor.role or "").strip().lower() not in {"admin", "registrar"} and not actor.is_superuser:
        db.rollback()
        raise missing
    # This probe is only a hint; every relation and role is re-read under
    # locks below before any patient data is returned.
    hint = (
        db.query(VisitInvitationDelivery.patient_id, VisitInvitationDelivery.visit_id, VisitInvitationDelivery.id)
        .join(NotificationEvent, NotificationEvent.entity_id == VisitInvitationDelivery.id.cast(NotificationEvent.entity_id.type))
        .join(NotificationDelivery, NotificationDelivery.event_id == NotificationEvent.id)
        .filter(NotificationEvent.correlation_id == handle,
                NotificationEvent.source_module == "visit_confirmation_secure",
                NotificationEvent.entity_type == "visit_invitation_delivery",
                NotificationDelivery.recipient_id == actor.id)
        .first()
    )
    if hint is None or hint.patient_id is None or hint.visit_id is None:
        db.rollback()
        raise missing
    try:
        patient = _lock_invitation_patient(db, hint.patient_id)
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Задача временно недоступна", headers={"Cache-Control": "private, no-store"}) from None
    visit = db.query(Visit).filter(Visit.id == hint.visit_id).populate_existing().with_for_update().first()
    intent = db.query(VisitInvitationDelivery).filter(VisitInvitationDelivery.id == hint.id).populate_existing().with_for_update().first()
    authorized = (
        db.query(NotificationDelivery.id)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(NotificationEvent.correlation_id == handle,
                NotificationEvent.source_module == "visit_confirmation_secure",
                NotificationEvent.entity_type == "visit_invitation_delivery",
                NotificationEvent.entity_id == str(hint.id), NotificationDelivery.recipient_id == actor.id)
        .with_for_update().first()
    )
    if (not authorized or patient is None or visit is None or intent is None
        or intent.patient_id != patient.id or intent.visit_id != visit.id
        or intent.state != "sent" or intent.channel != "phone" or visit.visit_date is None or not _valid_visit(visit, patient)
        or intent.owner_generation != patient.notification_owner_generation
        or intent.context_epoch != visit.confirmation_context_epoch
        or not hmac.compare_digest(intent.token_digest, _digest(visit.confirmation_token))):
        db.rollback()
        raise missing
    result = VisitInvitationTaskResponse(
        visit_id=visit.id, patient_name=patient.short_name(), patient_phone=patient.phone,
        visit_date=visit.visit_date.isoformat(), visit_time=visit.visit_time,
    )
    entry = _build_patient_access_entry(
        db, actor_user=actor, subject_patient_id=patient.id, resource_type="visit_invitation_task",
        resource_id=str(visit.id), action="view", request=request,
    )
    if entry is None:
        db.rollback()
        raise missing
    db.add(entry)
    try:
        check_profile_bearer(db, actor, bearer)
        check_bearer_expiry(bearer)
        db.commit()
    except ProfileBearerInvalid:
        db.rollback()
        raise missing from None
    return result


class VisitInvitationRecoveryResponse(BaseModel):
    visit_id: int


@_invitation_read_router.get("/visit-invitation-recoveries/{handle}", response_model=VisitInvitationRecoveryResponse)
def read_visit_invitation_recovery(
    handle: str, request: Request, response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
):
    """Resolve a neutral recovery handle for its current Admin recipient."""
    from uuid import UUID

    from app.api.v1.endpoints.visit_confirmation import _reissue_audit
    from app.models.doctor_price_override import DoctorPriceOverride
    from app.models.notification import NotificationDelivery, NotificationEvent
    from app.models.visit_invitation_delivery import VisitInvitationApprovalRecovery
    from app.services.notification_platform_service import NotificationPlatformService
    from app.services.visit_invitation_delivery import (
        InvitationRuntimeUnavailable,
        _lock_invitation_patient,
        _recovery_matches_token,
        _valid_visit,
        pin_invitation_runtime,
    )

    response.headers["Cache-Control"] = "private, no-store"
    missing = HTTPException(status_code=404, detail="Задача недоступна", headers={"Cache-Control": "private, no-store"})
    try:
        if str(UUID(handle)) != handle:
            raise missing
        pin_invitation_runtime(db)
        bearer = capture_profile_bearer(request, current_user)
        actor = db.query(User).filter(User.id == bearer.user_id).populate_existing().with_for_update().first()
        if actor is None:
            raise missing
        check_profile_bearer(db, actor, bearer)
        if not actor.is_superuser and (actor.role or "").strip().lower() != "admin":
            raise missing
        hint = (db.query(VisitInvitationApprovalRecovery.patient_id, VisitInvitationApprovalRecovery.visit_id,
                         VisitInvitationApprovalRecovery.id)
                .join(NotificationEvent, NotificationEvent.entity_id == VisitInvitationApprovalRecovery.id.cast(NotificationEvent.entity_id.type))
                .join(NotificationDelivery, NotificationDelivery.event_id == NotificationEvent.id)
                .filter(NotificationEvent.correlation_id == handle,
                        NotificationEvent.source_module == "visit_confirmation_recovery",
                        NotificationEvent.entity_type == "visit_invitation_approval_recovery",
                        NotificationDelivery.recipient_type == "user",
                        NotificationDelivery.channel == NotificationPlatformService.INBOX_CHANNEL,
                        NotificationDelivery.recipient_id == actor.id).first())
        if hint is None or hint.patient_id is None or hint.visit_id is None:
            raise missing
        patient = _lock_invitation_patient(db, hint.patient_id)
        visit = db.query(Visit).filter(Visit.id == hint.visit_id).populate_existing().with_for_update().first()
        recovery = db.query(VisitInvitationApprovalRecovery).filter(VisitInvitationApprovalRecovery.id == hint.id).populate_existing().with_for_update().first()
        override = (db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id == recovery.override_id)
                    .populate_existing().with_for_update(nowait=True).first()) if recovery is not None and recovery.override_id is not None else None
        recipient = (db.query(NotificationDelivery.id).join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
                     .filter(NotificationEvent.correlation_id == handle,
                             NotificationEvent.source_module == "visit_confirmation_recovery",
                             NotificationEvent.entity_type == "visit_invitation_approval_recovery",
                             NotificationEvent.entity_id == str(hint.id),
                             NotificationDelivery.recipient_type == "user",
                             NotificationDelivery.channel == NotificationPlatformService.INBOX_CHANNEL,
                             NotificationDelivery.recipient_id == actor.id)
                     .with_for_update().first())
        if (not recipient or patient is None or visit is None or recovery is None or override is None
            or patient.is_deleted or recovery.patient_id != patient.id or recovery.visit_id != visit.id
            or visit.patient_id != patient.id or visit.status != "pending_confirmation"
            or recovery.state != "dispatched" or patient.notification_owner_generation != recovery.owner_generation
            or visit.confirmation_context_epoch != recovery.context_epoch or override.status != "approved"
            or override.approved_by != recovery.actor_user_id_snapshot or override.visit_id != visit.id
            or not _recovery_matches_token(recovery, visit) or _valid_visit(visit, patient)):
            raise missing
        result = VisitInvitationRecoveryResponse(visit_id=visit.id)
        _reissue_audit(db, actor, visit.id, "visit_invitation_recovery_viewed")
        check_profile_bearer(db, actor, bearer)
        check_bearer_expiry(bearer)
        db.commit()
        return result
    except (ProfileBearerInvalid, ValueError):
        db.rollback()
        raise missing from None
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Задача временно недоступна", headers={"Cache-Control": "private, no-store"}) from None
    except HTTPException:
        db.rollback()
        raise


router.include_router(_invitation_read_router)


def _is_admin_or_superuser(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False)) or (
        str(getattr(user, "role", "")).strip().lower() == "admin"
    )


def _active_doctor_for_user(db: Session, user: User) -> Doctor | None:
    return (
        db.query(Doctor)
        .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
        .first()
    )


def _assert_doctor_owns_visit(
    *, db: Session, current_user: User, visit: Visit
) -> None:
    if _is_admin_or_superuser(current_user):
        return

    doctor = _active_doctor_for_user(db, current_user)
    if doctor is None or visit.doctor_id != doctor.id:
        # Avoid confirming whether an unassigned visit belongs to another patient.
        raise HTTPException(status_code=404, detail=t("visit.not_found"))


def _assert_doctor_can_notify_patient_visit(
    *,
    db: Session,
    current_user: User,
    patient_id: int,
    related_entity_type: str | None,
    related_entity_id: int | None,
) -> None:
    if _is_admin_or_superuser(current_user):
        return
    if related_entity_type != "visit" or related_entity_id is None:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))

    visit = db.query(Visit).filter(Visit.id == related_entity_id).first()
    if visit is None or visit.patient_id != patient_id:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))
    _assert_doctor_owns_visit(db=db, current_user=current_user, visit=visit)


def _combine_date_and_time(date_value, time_value: str | None) -> datetime:
    if date_value is None:
        return datetime.now(UTC)

    if not time_value:
        return datetime.combine(date_value, datetime.min.time())

    try:
        parsed_time = datetime.strptime(time_value, "%H:%M").time()
    except ValueError:
        logger.warning(
            "[Notifications] falling back to midnight for invalid visit time",
            extra={"date": date_value.isoformat(), "time": time_value},
        )
        parsed_time = datetime.min.time()

    return datetime.combine(date_value, parsed_time)


def _validate_recipient_scope(
    *,
    platform_service,
    current_user: User,
    recipient_id: int | None,
    recipient_type: str | None,
) -> None:
    expected_recipient_id = current_user.id

    if recipient_id is not None and recipient_id != expected_recipient_id:
        logger.warning(
            "[Notifications] rejected cross-recipient inbox request",
            extra={
                "current_user_id": current_user.id,
                "requested_recipient_id": recipient_id,
                "requested_recipient_type": recipient_type,
            },
        )
        raise HTTPException(status_code=403, detail="Нет прав доступа")


def get_or_create_notification_settings(db: Session, user_id: int):
    settings = crud_user_notification_settings.get_by_user_id(db, user_id=user_id)
    if settings:
        return settings

    profile = crud_user_profile.get_by_user_id(db, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль пользователя не найден")

    create_data = UserNotificationSettingsCreate(user_id=user_id, profile_id=profile.id)
    return crud_user_notification_settings.create(db, obj_in=create_data)


def get_or_create_user_preferences(db: Session, user_id: int):
    preferences = (
        db.query(UserPreferences)
        .filter(UserPreferences.user_id == user_id)
        .first()
    )
    if preferences:
        return preferences

    profile = crud_user_profile.get_by_user_id(db, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль пользователя не найден")

    preferences = UserPreferences(
        user_id=user_id,
        profile_id=profile.id,
    )
    db.add(preferences)
    db.commit()
    db.refresh(preferences)
    return preferences


def _assert_notification_policy_access(current_user: User, user_id: int) -> None:
    if current_user.id != user_id and (
        not hasattr(current_user, "role") or current_user.role != "Admin"
    ):
        raise HTTPException(status_code=403, detail="Нет прав доступа")


def _parse_policy_datetime(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field_name} must be ISO datetime string")
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} has invalid ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _normalize_realtime_control(control: Any, *, field_name: str) -> bool | dict[str, Any]:
    if isinstance(control, bool):
        return control
    if not isinstance(control, dict):
        raise HTTPException(status_code=422, detail=f"{field_name} must be boolean or object")

    normalized: dict[str, Any] = {}
    for key in ("enabled", "realtime_enabled", "desktop"):
        value = control.get(key)
        if isinstance(value, bool):
            normalized[key] = value

    channels = control.get("channels")
    if channels is not None:
        if not isinstance(channels, dict):
            raise HTTPException(status_code=422, detail=f"{field_name}.channels must be an object")
        normalized_channels: dict[str, bool] = {}
        for channel_name in ("desktop", "push", "email", "sms"):
            channel_value = channels.get(channel_name)
            if isinstance(channel_value, bool):
                normalized_channels[channel_name] = channel_value
        if normalized_channels:
            normalized["channels"] = normalized_channels

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} has no supported keys (enabled/realtime_enabled/desktop/channels)",
        )
    return normalized


def _normalize_notification_policy_payload(
    *,
    policy_data: dict[str, Any],
    platform_service,
) -> dict[str, Any]:
    supported_keys = {
        "muted_until",
        "snooze_until",
        "dnd",
        "event_controls",
        "family_controls",
        "channel_controls",
    }
    normalized_policy: dict[str, Any] = {}

    for key in supported_keys:
        if key not in policy_data:
            continue
        value = policy_data.get(key)
        if key in {"muted_until", "snooze_until"}:
            parsed_datetime = _parse_policy_datetime(value, field_name=key)
            if parsed_datetime:
                normalized_policy[key] = parsed_datetime
            continue

        if key == "dnd":
            if value is None:
                continue
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail="dnd must be an object")
            dnd: dict[str, Any] = {}
            if "enabled" in value:
                if not isinstance(value["enabled"], bool):
                    raise HTTPException(status_code=422, detail="dnd.enabled must be boolean")
                dnd["enabled"] = value["enabled"]
            if "always_on" in value:
                if not isinstance(value["always_on"], bool):
                    raise HTTPException(status_code=422, detail="dnd.always_on must be boolean")
                dnd["always_on"] = value["always_on"]
            for time_key in ("start", "end"):
                if time_key not in value:
                    continue
                time_value = value[time_key]
                if time_value is None:
                    continue
                if not isinstance(time_value, str) or not _TIME_PATTERN.match(time_value):
                    raise HTTPException(status_code=422, detail=f"dnd.{time_key} must be HH:MM")
                dnd[time_key] = time_value
            if dnd:
                normalized_policy["dnd"] = dnd
            continue

        if key == "channel_controls":
            if value is None:
                continue
            normalized_policy["channel_controls"] = _normalize_realtime_control(
                value,
                field_name="channel_controls",
            )
            continue

        if key in {"event_controls", "family_controls"}:
            if value is None:
                continue
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail=f"{key} must be an object")
            normalized_controls: dict[str, Any] = {}
            for raw_name, raw_control in value.items():
                if not isinstance(raw_name, str):
                    continue
                if key == "event_controls":
                    normalized_name = platform_service.normalize_event_type(raw_name)
                else:
                    normalized_name = platform_service.normalize_slug(raw_name) or ""
                if not normalized_name:
                    continue
                normalized_controls[normalized_name] = _normalize_realtime_control(
                    raw_control,
                    field_name=f"{key}.{raw_name}",
                )
            if normalized_controls:
                normalized_policy[key] = normalized_controls

    return normalized_policy


def _notification_bearer(request: Request | None, current_user: User):
    if request is None:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    try:
        return capture_profile_bearer(request, current_user)
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=403, detail="Доступ запрещён") from exc


@router.post("/send-appointment-reminder", response_model=dict[str, Any])
async def send_appointment_reminder(
    background_tasks: BackgroundTasks,
    patient_id: int,
    appointment_date: datetime,
    doctor_name: str,
    department: str,
    current_user: User = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db),
    request: Request = None,
    visit_id: int | None = None,
):
    """Queue a neutral reminder for one explicit, currently authorized Visit."""
    # The legacy name/department inputs are accepted but never trusted or sent.
    del doctor_name, department
    if visit_id is None:
        if not _is_admin_or_superuser(current_user):
            raise HTTPException(status_code=404, detail=t("visit.not_found"))
        raise HTTPException(status_code=409, detail="Укажите визит для напоминания")
    visit = visit_crud.get_visit(db, visit_id)
    if visit is None or visit.patient_id != patient_id:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))
    _assert_doctor_owns_visit(db=db, current_user=current_user, visit=visit)
    if visit.visit_date != appointment_date.date():
        raise HTTPException(status_code=409, detail="Дата визита изменилась")
    intent = create_patient_notification_intent(
        db, bearer=_notification_bearer(request, current_user),
        purpose="appointment_reminder", visit_id=visit_id,
        requested_patient_id=patient_id,
    )
    background_tasks.add_task(dispatch_patient_notification_intent, intent)
    return {"message": "Попытка уведомления поставлена в очередь", "queued": True,
            "eligible_channels": list(intent.eligible_channels)}


@router.post("/send-visit-confirmation", response_model=dict[str, Any])
async def send_visit_confirmation(
    background_tasks: BackgroundTasks,
    visit_id: int,
    queue_number: int | None = None,
    current_user: User = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Queue a neutral notice; details stay in the patient's protected view."""
    del queue_number  # Caller-supplied queue information is never transported.
    visit = visit_crud.get_visit(db, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))
    _assert_doctor_owns_visit(db=db, current_user=current_user, visit=visit)
    intent = create_patient_notification_intent(
        db, bearer=_notification_bearer(request, current_user),
        purpose="visit_confirmation", visit_id=visit_id,
    )
    background_tasks.add_task(dispatch_patient_notification_intent, intent)
    return {"message": "Попытка уведомления поставлена в очередь", "queued": True,
            "eligible_channels": list(intent.eligible_channels)}


@router.post("/send-payment-notification", response_model=dict[str, Any])
async def send_payment_notification(
    background_tasks: BackgroundTasks,
    visit_id: int,
    amount: float,
    currency: str,
    current_user: User = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db),
    request: Request = None,
    payment_id: int | None = None,
):
    """Queue a neutral notice for a confirmed payment belonging to this Visit."""
    del amount, currency  # Legacy caller values do not establish a payment.
    visit = visit_crud.get_visit(db, visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))
    _assert_doctor_owns_visit(db=db, current_user=current_user, visit=visit)
    intent = create_patient_notification_intent(
        db, bearer=_notification_bearer(request, current_user),
        purpose="payment_notification", visit_id=visit_id, payment_id=payment_id,
    )
    background_tasks.add_task(dispatch_patient_notification_intent, intent)
    return {"message": "Попытка уведомления поставлена в очередь", "queued": True,
            "eligible_channels": list(intent.eligible_channels)}


@router.post("/send-queue-update", response_model=dict[str, Any])
async def send_queue_update(
    background_tasks: BackgroundTasks,
    department: str,
    current_number: int,
    estimated_wait: str,
    current_user: User = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db),
):
    """Отправка обновления очереди"""
    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_queue_update,
        department,
        current_number,
        estimated_wait,
        None,
        db,
    )

    return {
        "message": "Обновление очереди отправлено",
        "department": department,
        "current_number": current_number,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/send-system-alert", response_model=dict[str, Any])
async def send_system_alert(
    background_tasks: BackgroundTasks,
    alert_type: str,
    message: str,
    body: SendSystemAlertRequest = SendSystemAlertRequest(),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Отправка системного оповещения (только для админов)"""
    details = body.details.model_dump(exclude_none=True) if body.details else None
    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_system_alert,
        alert_type,
        message,
        details,
        db,
        current_user.id,
        current_user.role,
    )

    return {
        "message": "Системное оповещение отправлено",
        "alert_type": alert_type,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/test-notifications", response_model=dict[str, Any])
async def test_notifications(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Report diagnostic endpoint status without sending to external recipients."""
    return {
        "message": "Диагностика не отправляет уведомления внешним получателям",
        "queued": 0,
        "external_delivery": False,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.get("/notification-status", response_model=dict[str, Any])
async def get_notification_status(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Получение статуса настроек уведомлений"""
    return {
        "email": {
            "configured": bool(
                notification_sender_service.smtp_username
                and notification_sender_service.smtp_password
            ),
            "server": notification_sender_service.smtp_server,
            "port": notification_sender_service.smtp_port,
        },
        "telegram": {
            "configured": bool(notification_sender_service.telegram_bot_token),
            "bot_token": "***" if notification_sender_service.telegram_bot_token else None,
            "delivery_mode": "linked_chat_only",
        },
        "sms": {
            "configured": bool(
                notification_sender_service.sms_api_key and notification_sender_service.sms_api_url
            ),
            "api_url": notification_sender_service.sms_api_url,
        },
    }


# Управление шаблонами уведомлений
_TEMPLATE_DETAIL_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {"detail": {"type": "string"}},
}
_TEMPLATE_VALIDATION_SCHEMA = {
    "type": "object",
    "required": ["error", "message", "detail"],
    "properties": {
        "error": {"type": "string"},
        "message": {"type": "string"},
        "detail": {"type": "array", "items": {"type": "object"}},
    },
}
_TEMPLATE_CONFLICT_RESPONSE = {
    "description": "Конфликт шаблона",
    "content": {"application/json": {"schema": _TEMPLATE_DETAIL_SCHEMA}},
}
_TEMPLATE_SERVER_ERROR_RESPONSE = {"description": "Ошибка обработки или базы данных"}
_TEMPLATE_DATABASE_UNAVAILABLE_RESPONSE = {"description": "Сервис базы данных недоступен"}


@router.get("/templates", response_model=list[NotificationTemplate])
async def get_notification_templates(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Получение списка шаблонов уведомлений"""
    return crud_notification_template.get_multi(db)


@router.post(
    "/templates",
    response_model=NotificationTemplate,
    responses={
        409: _TEMPLATE_CONFLICT_RESPONSE,
        422: {
            "description": "Ошибка валидации запроса",
            "content": {"application/json": {"schema": _TEMPLATE_VALIDATION_SCHEMA}},
        },
        500: _TEMPLATE_SERVER_ERROR_RESPONSE,
        503: _TEMPLATE_DATABASE_UNAVAILABLE_RESPONSE,
    },
)
async def create_notification_template(
    template_data: NotificationTemplateCreate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Создание шаблона уведомления"""
    try:
        return crud_notification_template.create_atomic(db, obj_in=template_data)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Конфликт шаблона") from exc


@router.put(
    "/templates/{template_id}",
    response_model=NotificationTemplate,
    responses={
        404: {
            "description": "Шаблон не найден",
            "content": {"application/json": {"schema": _TEMPLATE_DETAIL_SCHEMA}},
        },
        409: _TEMPLATE_CONFLICT_RESPONSE,
        422: {
            "description": "Ошибка валидации запроса или полей шаблона",
            "content": {
                "application/json": {
                    "schema": {"oneOf": [_TEMPLATE_VALIDATION_SCHEMA, _TEMPLATE_DETAIL_SCHEMA]}
                }
            },
        },
        500: _TEMPLATE_SERVER_ERROR_RESPONSE,
        503: _TEMPLATE_DATABASE_UNAVAILABLE_RESPONSE,
    },
)
async def update_notification_template(
    template_id: int,
    template_data: NotificationTemplateUpdate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Обновление шаблона уведомления"""
    try:
        template = crud_notification_template.update_atomic(
            db, template_id=template_id, obj_in=template_data
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Некорректные поля шаблона") from exc
    except (IntegrityError, TemplateConcurrentUpdate) as exc:
        raise HTTPException(status_code=409, detail="Конфликт шаблона") from exc
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return template


@router.delete("/templates/{template_id}", response_model=dict[str, Any])
async def delete_notification_template(
    template_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Удаление шаблона уведомления"""
    template = crud_notification_template.get(db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    crud_notification_template.remove(db, id=template_id)
    return {"message": "Шаблон удален"}


# История уведомлений и inbox
@router.get("/inbox", response_model=NotificationInboxResponse)
@router.get("/history", response_model=NotificationInboxResponse)
async def get_notification_history(
    role: str | None = Query(None),
    status: str = Query("all"),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    department_key: str | None = Query(None),
    search: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение inbox/history текущего пользователя."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )

    return platform_service.get_inbox(
        current_user=current_user,
        role=role,
        status=status,
        event_type=event_type,
        severity=severity,
        department_key=department_key,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.get("/sync", response_model=NotificationInboxResponse)
async def sync_notifications(
    role: str | None = Query(None),
    status: str = Query("all"),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    department_key: str | None = Query(None),
    search: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cursor-based inbox resync."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    return platform_service.get_inbox(
        current_user=current_user,
        role=role,
        status=status,
        event_type=event_type,
        severity=severity,
        department_key=department_key,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_unread_notification_count(
    role: str | None = Query(None),
    department_key: str | None = Query(None),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-authoritative unread counts."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    return platform_service.get_unread_counts(
        current_user=current_user,
        role=role,
        department_key=department_key,
    )


@router.post("/{delivery_id}/seen", response_model=NotificationMutationResponse)
async def mark_notification_seen(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as seen."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.mark_seen(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление отмечено как просмотренное",
    )


@router.post("/{delivery_id}/read", response_model=NotificationMutationResponse)
async def mark_notification_read(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.mark_read(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление отмечено как прочитанное",
    )


@router.post("/{delivery_id}/archive", response_model=NotificationMutationResponse)
async def archive_notification(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive a notification."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.archive(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление архивировано",
    )


@router.post("/mark-all-read", response_model=NotificationMutationResponse)
async def mark_all_notifications_read(
    role: str | None = Query(None),
    department_key: str | None = Query(None),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    count = await platform_service.mark_all_read(
        current_user=current_user,
        role=role,
        department_key=department_key,
    )
    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id="mark-all-read",
        delivery_status="read",
        unread_count=unread_count,
        message=f"Отмечено как прочитанное: {count}",
    )


@router.get("/history/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Получение статистики уведомлений."""
    platform_service = get_notification_platform_service(db)
    stats = platform_service.get_stats(days=days)

    return NotificationStatsResponse(
        total_sent=stats["total_sent"],
        successful=stats["successful"],
        failed=stats["failed"],
        pending=stats["pending"],
        by_channel=stats["by_channel"],
        by_type=stats["by_type"],
        recent_activity=stats["recent_activity"],
    )


# Настройки уведомлений
@router.get("/settings/{user_id}", response_model=UserNotificationSettingsResponse)
async def get_user_notification_settings(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение настроек уведомлений пользователя"""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)

    # Используем UserNotificationSettings
    return get_or_create_notification_settings(db, user_id)


@router.put("/settings/{user_id}", response_model=UserNotificationSettingsResponse)
async def update_user_notification_settings(
    user_id: int,
    settings_data: UserNotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление настроек уведомлений пользователя"""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)

    settings = get_or_create_notification_settings(db, user_id)

    return crud_user_notification_settings.update(db, db_obj=settings, obj_in=settings_data)


@router.get("/settings/{user_id}/policy", response_model=dict[str, Any])
async def get_user_notification_policy(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение runtime policy-override для anti-noise (mute/snooze/DND + controls)."""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)
    preferences = get_or_create_user_preferences(db, user_id)
    security_settings = preferences.security_settings if isinstance(preferences.security_settings, dict) else {}
    policy = security_settings.get("notification_policy")
    if not isinstance(policy, dict):
        policy = {}
    return {
        "user_id": user_id,
        "policy": policy,
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
    }


@router.put("/settings/{user_id}/policy", response_model=dict[str, Any])
async def update_user_notification_policy(
    user_id: int,
    body: UpdateNotificationPolicyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление runtime policy-override для anti-noise (mute/snooze/DND + controls)."""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)
    platform_service = get_notification_platform_service(db)
    policy_data = body.model_dump(exclude_none=True)
    normalized_policy = _normalize_notification_policy_payload(
        policy_data=policy_data,
        platform_service=platform_service,
    )

    preferences = get_or_create_user_preferences(db, user_id)
    security_settings = preferences.security_settings if isinstance(preferences.security_settings, dict) else {}
    security_settings["notification_policy"] = normalized_policy
    preferences.security_settings = security_settings
    db.add(preferences)
    db.commit()
    db.refresh(preferences)

    return {
        "user_id": user_id,
        "policy": normalized_policy,
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
    }


# Отправка уведомлений с шаблонами
@router.post("/send", response_model=dict[str, Any])
async def send_notification(
    background_tasks: BackgroundTasks,
    request: SendNotificationRequest,
    current_user: User = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db),
):
    """Поставить попытки отправки в фон; ответ не подтверждает доставку.

    При ошибке рендеринга шаблона сообщение не отправляется, а попытка
    отмечается как неудачная в истории уведомлений.
    """
    if request.scheduled_at is not None:
        raise HTTPException(
            status_code=422,
            detail="Отложенная отправка пока не поддерживается; сообщение не поставлено в очередь",
        )
    if request.recipient_type != "patient":
        raise HTTPException(
            status_code=422,
            detail="Для этого endpoint поддерживаются только получатели типа patient",
        )
    if request.recipient_id is None:
        raise HTTPException(status_code=422, detail="recipient_id обязателен")
    if str(request.priority).strip().lower() not in {"low", "normal", "high", "urgent"}:
        raise HTTPException(status_code=422, detail="Неподдерживаемый приоритет уведомления")

    channels = list(dict.fromkeys(str(channel).strip().lower() for channel in request.channels))
    supported_channels = {"email", "sms", "telegram"}
    if not channels or any(channel not in supported_channels for channel in channels):
        raise HTTPException(status_code=422, detail="Неподдерживаемый канал уведомления")

    _assert_doctor_can_notify_patient_visit(
        db=db,
        current_user=current_user,
        patient_id=request.recipient_id,
        related_entity_type=request.related_entity_type,
        related_entity_id=request.related_entity_id,
    )
    patient = patient_crud.get(db, id=request.recipient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    telegram_link = (
        db.query(TelegramUser)
        .filter(
            TelegramUser.patient_id == patient.id,
            TelegramUser.active.is_(True),
            TelegramUser.blocked.is_(False),
            TelegramUser.notifications_enabled.is_(True),
        )
        .order_by(TelegramUser.id.desc())
        .first()
    )
    queued_channels = []
    for channel in channels:
        # Получаем контакт получателя
        contact = None
        if channel == "email":
            contact = patient.email
        elif channel == "sms":
            contact = patient.phone
        elif channel == "telegram" and telegram_link:
            contact = str(telegram_link.chat_id)

        if not contact:
            continue

        # Отправляем в фоновом режиме
        background_tasks.add_task(
            notification_sender_service.send_templated_notification,
            db=db,
            notification_type=request.notification_type,
            channel=channel,
            recipient_contact=contact,
            template_data=request.template_data,
            recipient_type=request.recipient_type,
            recipient_id=request.recipient_id,
            related_entity_type=request.related_entity_type,
            related_entity_id=request.related_entity_id,
            priority=request.priority,
        )
        queued_channels.append(channel)

    return {
        "message": "Попытки отправки поставлены в очередь",
        "queued": len(queued_channels),
        "channels": queued_channels,
    }


@router.post("/send-bulk", response_model=dict[str, Any])
async def send_bulk_notification(
    background_tasks: BackgroundTasks,
    request: BulkNotificationRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Массовая отправка уведомлений"""
    if request.recipient_type != "patient":
        raise HTTPException(
            status_code=422,
            detail="Для этого endpoint поддерживаются только получатели типа patient",
        )
    if str(request.priority).strip().lower() not in {"low", "normal", "high", "urgent"}:
        raise HTTPException(status_code=422, detail="Неподдерживаемый приоритет уведомления")
    channels = list(dict.fromkeys(str(channel).strip().lower() for channel in request.channels))
    supported_channels = {"email", "sms", "telegram"}
    if not channels or any(channel not in supported_channels for channel in channels):
        raise HTTPException(status_code=422, detail="Неподдерживаемый канал уведомления")

    recipients = []

    # Формируем список получателей
    for recipient_id in dict.fromkeys(request.recipient_ids):
        patient = patient_crud.get(db, id=recipient_id)
        if patient:
            telegram_link = (
                db.query(TelegramUser)
                .filter(
                    TelegramUser.patient_id == patient.id,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                    TelegramUser.notifications_enabled.is_(True),
                )
                .order_by(TelegramUser.id.desc())
                .first()
            )
            recipients.append(
                {
                    "id": patient.id,
                    "type": "patient",
                    "email": patient.email,
                    "phone": patient.phone,
                    "telegram": str(telegram_link.chat_id) if telegram_link else None,
                    "name": patient.full_name
                    or f"{patient.first_name} {patient.last_name}",
                }
            )

    # Отправляем в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_bulk_notification,
        db=db,
        notification_type=request.notification_type,
        channels=channels,
        recipients=recipients,
        template_data=request.template_data,
        priority=request.priority,
    )
    return {
        "message": "Массовая отправка запущена",
        "recipients_count": len(recipients),
        "channels": channels,
    }
