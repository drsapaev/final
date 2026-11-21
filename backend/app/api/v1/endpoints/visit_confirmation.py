"""
API endpoints для подтверждения визитов через Telegram и PWA.
Публичные эндпоинты без авторизации (используют токены).
"""

import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.core.config import settings
from app.core.roles import normalize_role_value
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_group_without_pending,
)
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_profile_bearer,
)
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)
from app.services.visit_invitation_delivery import (
    InvitationContextChanged,
    InvitationRuntimeUnavailable,
    pin_invitation_runtime,
    stage_visit_invitation,
)

router = APIRouter()


class TelegramConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    telegram_user_id: str | None = None
    telegram_username: str | None = None


class PWAConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    patient_phone: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class VisitInfoRequest(BaseModel):
    token: str


class VisitInfoServiceItem(BaseModel):
    name: str
    code: str | None
    quantity: int
    price: float
    total: float


class VisitInfoResponse(BaseModel):
    """Patient-safe public visit card (GET/POST /visits/info).

    PR 3390 review P2 + PR 3407 delta review P2: deliberately does NOT
    include ``notes``. The card is bearer-token-addressed and public, so
    the internal clinical/admin field (``diagnosis: …``, cancel reasons,
    force-reopen audit lines) is dropped from the service projection
    itself, and BOTH routes (the new POST and the legacy GET) are
    additionally filtered through this model — defense in depth against
    a future regression re-adding the field to the shared card.
    """

    success: bool
    visit_id: int
    status: str
    patient_name: str
    doctor_name: str
    visit_date: str
    visit_time: str | None
    department: str | None
    discount_mode: str | None
    services: list[VisitInfoServiceItem]
    total_amount: float
    currency: str | None
    confirmation_expires_at: str | None


class ConfirmationResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    patient_name: str
    visit_date: str
    visit_time: str | None
    queue_numbers: list[dict[str, Any]] | None = None
    print_tickets: list[dict[str, Any]] | None = None


def _raise_http_error(exc: VisitConfirmationDomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=exc.headers)


class TelegramVisitActionDenied(BaseModel):
    detail: str


_TELEGRAM_DENIED_RESPONSE = {
    403: {
        "model": TelegramVisitActionDenied,
        "description": "Telegram actions require an authenticated bot update.",
        "headers": {"Cache-Control": {"schema": {"type": "string"}}},
    }
}


@router.post(
    "/telegram/visits/confirm", status_code=403, response_model=TelegramVisitActionDenied,
    responses=_TELEGRAM_DENIED_RESPONSE, deprecated=True,
)
def confirm_visit_by_telegram(
    request_body: TelegramConfirmRequest,
):
    """A claimed Telegram user ID in an unauthenticated request is untrusted.

    Telegram updates are handled by the authenticated webhook or polling
    transport and invoke the service directly with the verified actor.
    """
    raise HTTPException(
        status_code=403,
        detail="Подтверждение доступно только из привязанного чата Telegram",
        headers={"Cache-Control": "private, no-store"},
    )


class TelegramCancelRequest(BaseModel):
    token: str = Field(..., min_length=10)
    telegram_user_id: str | None = None


class CancelVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    patient_name: str


@router.post(
    "/telegram/visits/cancel", status_code=403, response_model=TelegramVisitActionDenied,
    responses=_TELEGRAM_DENIED_RESPONSE, deprecated=True,
)
def cancel_visit_by_telegram(
    request_body: TelegramCancelRequest,
):
    """Reject caller-asserted Telegram identities on the public API."""
    raise HTTPException(
        status_code=403,
        detail="Отмена доступна только из привязанного чата Telegram",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/patient/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_pwa(
    request_body: PWAConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Подтверждение визита через PWA по токену."""
    service = VisitConfirmationService(db)
    source_ip = request.client.host if request.client else request_body.ip_address
    user_agent = request.headers.get("user-agent") or request_body.user_agent

    try:
        result = service.confirm_by_pwa(
            token=request_body.token,
            patient_phone=request_body.patient_phone,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return ConfirmationResponse(**result)
    except VisitConfirmationDomainError as exc:
        if exc.status_code >= 500:
            # This service wraps raw exception text in its 5xx detail.
            # Do not expose that text on the public PWA confirmation route.
            raise HTTPException(
                status_code=exc.status_code,
                detail="Не удалось подтвердить визит",
                headers=exc.headers,
            ) from None
        _raise_http_error(exc)


@router.get("/visits/info/{token}", response_model=VisitInfoResponse)
def get_visit_info_by_token(
    token: str, response: Response, db: Session = Depends(get_db)
):
    """Получение информации о визите по токену (без подтверждения).

    PR 3407 delta review P2: the legacy GET returns the same patient-safe
    card as the POST — the raw ``dict[str, Any]`` response_model is gone,
    so the shared service projection cannot leak internal fields here
    even if it regresses.

    PR 3417 review residual P2: the card is bearer-capability PHI, so the
    response is marked ``Cache-Control: private, no-store`` (same policy
    as dental clinical content), and the 5xx error path is sanitized
    exactly like the POST's — the service wraps raw exception text
    (SQLAlchemy/DB internals) into its 500 detail, which must never
    reach a public bearer-token caller.
    """
    # Bearer-capability PHI must live only in the current response: keep
    # browsers and intermediaries from caching the visit card.
    response.headers["Cache-Control"] = "private, no-store"
    service = VisitConfirmationService(db)

    try:
        return service.get_visit_info(token)
    except VisitConfirmationDomainError as exc:
        # Mirror the POST route: 5xx details from this service carry raw
        # exception text; publish a generic message instead.
        if exc.status_code >= 500:
            raise HTTPException(
                status_code=exc.status_code,
                detail="Не удалось получить информацию о визите",
                headers=exc.headers,
            ) from None
        _raise_http_error(exc)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Не удалось получить информацию о визите"
        ) from None


@router.post("/visits/info", response_model=VisitInfoResponse)
def post_visit_info_by_token(
    request_body: VisitInfoRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Read a public visit card without putting its bearer token in the URL."""
    # Same PHI no-store policy as the legacy GET (PR 3417 review residual P2).
    response.headers["Cache-Control"] = "private, no-store"
    service = VisitConfirmationService(db)

    try:
        return service.get_visit_info(request_body.token)
    except VisitConfirmationDomainError as exc:
        # The service includes raw exception text in its 5xx detail; both
        # public routes now publish the same generic message (the legacy
        # GET mirrors this sanitization since the PR 3417 review).
        detail = (
            "Не удалось получить информацию о визите"
            if exc.status_code >= 500
            else exc.detail
        )
        raise HTTPException(
            status_code=exc.status_code, detail=detail, headers=exc.headers
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500, detail="Не удалось получить информацию о визите"
        ) from None


_REISSUE_NO_STORE = {"Cache-Control": "private, no-store"}


class _ReissueRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                response = await original(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Некорректный запрос"}, headers=_REISSUE_NO_STORE)
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **_REISSUE_NO_STORE}
                raise
            response.headers.update(_REISSUE_NO_STORE)
            return response

        return handler


_reissue_router = APIRouter(route_class=_ReissueRoute)


class InvitationReissueServiceItem(BaseModel):
    name: str
    code: str | None
    quantity: int
    price: float
    total: float


class InvitationReissueReview(BaseModel):
    visit_id: int
    patient_id: int
    patient_name: str
    visit_date: str
    visit_time: str | None
    owner_generation: int
    context_epoch: int
    channel: str
    services: list[InvitationReissueServiceItem]
    total_amount: float
    currency: str | None
    token: str


class InvitationReissueRequest(BaseModel):
    expected_patient_id: int = Field(gt=0, strict=True)
    expected_owner_generation: int = Field(gt=0, strict=True)
    expected_context_epoch: int = Field(gt=0, strict=True)
    channel: Literal["auto", "telegram", "pwa", "phone"]
    token: str = Field(min_length=20, max_length=128, strict=True)


class InvitationReissueResponse(BaseModel):
    delivery_id: int
    state: Literal["pending", "unknown", "sent", "cancelled"]
    idempotent_replay: bool


def _locked_reissue_subject(db: Session, visit_id: int, bearer, *, financial_guard: bool = False):
    """Lock User(s), Patient, then Visit; the initial IDs are only a hint."""
    try:
        require_patient_subject_visibility(db)
    except PatientSubjectLockError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Контекст визита недоступен") from None
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("UPDATE users SET id=id WHERE 0")
    hint = (db.query(Visit.patient_id, Patient.user_id)
            .join(Patient, Patient.id == Visit.patient_id).filter(Visit.id == visit_id).first())
    if hint is None:
        raise HTTPException(status_code=404, detail="Визит недоступен")
    ids = {bearer.user_id}
    if hint.user_id is not None:
        ids.add(hint.user_id)
    users = (db.query(User).filter(User.id.in_(sorted(ids))).order_by(User.id)
             .with_for_update().populate_existing().all())
    by_id = {row.id: row for row in users}
    actor = by_id.get(bearer.user_id)
    if actor is None or not actor.is_active or (
        not actor.is_superuser and normalize_role_value(actor.role) != "admin"
    ):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    check_profile_bearer(db, actor, bearer)
    if hint.user_id is not None and (hint.user_id not in by_id or not by_id[hint.user_id].is_active):
        raise HTTPException(status_code=409, detail="Контекст пациента недоступен")
    try:
        patient_active = lock_patient_subject(db, hint.patient_id)
    except PatientSubjectLockError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Контекст визита недоступен") from None
    patient = (db.query(Patient).filter(Patient.id == hint.patient_id)
               .populate_existing().first()) if patient_active else None
    if patient is None or patient.is_deleted or patient.user_id != hint.user_id:
        raise HTTPException(status_code=409, detail="Контекст визита изменился")
    if financial_guard:
        lock_group_without_pending(db, visit_id)
    visit = (db.query(Visit).filter(Visit.id == visit_id)
             .with_for_update().populate_existing().first())
    if (patient is None or visit is None or patient.is_deleted or visit.patient_id != patient.id
        or patient.user_id != hint.user_id or visit.status != "pending_confirmation"
        or patient.notification_owner_generation <= 0 or visit.confirmation_context_epoch <= 0):
        raise HTTPException(status_code=409, detail="Контекст визита изменился")
    return actor, patient, visit


def _reissue_audit(db: Session, actor: User, visit_id: int, action: str) -> None:
    db.add(AuditLog(
        action=action, event_type=action, entity_type="visit", entity_id=visit_id,
        actor_user_id=actor.id, actor_role=str(getattr(actor.role, "value", actor.role)),
        actor_type="staff", outcome="success", payload={},
    ))


def _reissue_review_snapshot(db: Session, patient: Patient, visit: Visit) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project the displayed review and an exact, locked signing context."""
    quote = PaymentInvariantService(db).compute_visit_quote(visit)
    # 0106 evidence is not yet versioned/immutable: 0130 must enable this
    # path with a monotonic decision version before benefit reviews ship.
    if quote.has_benefit:
        raise HTTPException(status_code=409, detail="Льгота требует повторной проверки")
    if quote.currency is None:
        raise HTTPException(status_code=409, detail="Валюта услуг требует проверки администратором")
    if not isinstance(quote.snapshot_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", quote.snapshot_digest):
        raise HTTPException(status_code=409, detail="Стоимость визита требует проверки")
    services = (db.query(VisitService).filter(VisitService.visit_id == visit.id)
                .order_by(VisitService.id).populate_existing().all())
    if ({item.id for item in services} != set(quote.line_totals) or visit.visit_date is None
        or any(item.price is None for item in services)):
        raise HTTPException(status_code=409, detail="Стоимость визита требует проверки")
    items = [{"id": item.id, "name": item.name, "code": item.code, "quantity": item.qty,
              "price": format(item.price, "f"), "total": format(quote.line_totals[item.id], "f")}
             for item in services]
    displayed = {"visit_id": visit.id, "patient_id": patient.id, "patient_name": patient.short_name(),
        "visit_date": visit.visit_date.isoformat(), "visit_time": visit.visit_time,
        "owner_generation": patient.notification_owner_generation, "context_epoch": visit.confirmation_context_epoch,
        "channel": visit.confirmation_channel or "auto", "currency": quote.currency,
        "services": [{key: (float(value) if key in {"price", "total"} else value)
                      for key, value in item.items() if key != "id"} for item in items],
        "total_amount": float(quote.total)}
    signed = {"displayed": {key: value for key, value in displayed.items() if key not in {"services", "total_amount"}},
              "items": items, "total_amount": format(quote.total, "f"), "financial_snapshot": quote.snapshot_digest,
              "confirmation_token_digest": (hashlib.sha256(visit.confirmation_token.encode()).hexdigest()
                                             if visit.confirmation_token else None),
              "confirmation_expires_at": (visit.confirmation_expires_at.isoformat()
                                          if visit.confirmation_expires_at else None)}
    return displayed, signed


def _reissue_review_token(actor: User, bearer, snapshot: dict[str, Any], expiry: int) -> str:
    if not bearer.jti or bearer.expires_at is None:
        raise HTTPException(status_code=401, detail="Сеанс недоступен")
    context = {"actor": actor.id, "auth_epoch": bearer.auth_epoch,
               "jti_digest": hashlib.sha256(bearer.jti.encode()).hexdigest(),
               "expiry": expiry, "snapshot": snapshot}
    payload = json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(settings.SECRET_KEY.encode(), b"visit-invitation-review-v1\0" + payload,
                         hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


@_reissue_router.post("/visits/{visit_id}/confirmation-reissue/review", response_model=InvitationReissueReview)
def review_invitation_reissue(
    visit_id: int, request: Request, db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
) -> InvitationReissueReview:
    try:
        bearer = capture_profile_bearer(request, current_user)
        pin_invitation_runtime(db)
        actor, patient, visit = _locked_reissue_subject(db, visit_id, bearer, financial_guard=True)
        displayed, snapshot = _reissue_review_snapshot(db, patient, visit)
        if not bearer.jti or bearer.expires_at is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        expiry = min(int(datetime.now(UTC).timestamp()) + 300, bearer.expires_at)
        result = InvitationReissueReview(**displayed, token=_reissue_review_token(actor, bearer, snapshot, expiry))
        _reissue_audit(db, actor, visit.id, "visit_invitation_reissue_reviewed")
        check_bearer_expiry(bearer)
        db.commit()
        return result
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен") from None
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Отправка временно недоступна") from None
    except FinancialFenceError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Визит сейчас недоступен") from None
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if code in {"40P01", "55P03"}:
            raise HTTPException(status_code=409, detail="Визит сейчас недоступен") from None
        raise HTTPException(status_code=500, detail="Не удалось проверить визит") from None
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось проверить визит") from None


@_reissue_router.post("/visits/{visit_id}/confirmation-reissue", response_model=InvitationReissueResponse)
def reissue_invitation(
    visit_id: int, payload: InvitationReissueRequest, request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"), db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
) -> InvitationReissueResponse:
    try:
        parsed_key = uuid.UUID(idempotency_key)
        if parsed_key.version != 4 or str(parsed_key) != idempotency_key.lower():
            raise ValueError("key")
        bearer = capture_profile_bearer(request, current_user)
        if not bearer.jti or bearer.expires_at is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        pin_invitation_runtime(db)
        actor, patient, visit = _locked_reissue_subject(db, visit_id, bearer, financial_guard=True)
        key_hash = hashlib.sha256(f"visit-invitation-reissue-key-v1:{actor.id}:{parsed_key}".encode()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps(["visit-invitation-reissue-v1", visit_id,
            payload.expected_patient_id, payload.expected_owner_generation, payload.expected_context_epoch,
            payload.channel, hashlib.sha256(payload.token.encode()).hexdigest(), bearer.auth_epoch,
            hashlib.sha256(bearer.jti.encode()).hexdigest()], separators=(",", ":")).encode()).hexdigest()
        previous = (db.query(VisitInvitationDelivery).filter(
            VisitInvitationDelivery.issuer_actor_id == actor.id,
            VisitInvitationDelivery.issuer_key_digest == key_hash).first())
        if previous is not None:
            if (not hmac.compare_digest(previous.issuer_fingerprint or "", fingerprint)
                or previous.patient_id != patient.id or previous.visit_id != visit.id
                or previous.owner_generation != patient.notification_owner_generation
                or previous.context_epoch != visit.confirmation_context_epoch
                or not visit.confirmation_token
                or not hmac.compare_digest(previous.token_digest, hashlib.sha256(visit.confirmation_token.encode()).hexdigest())
                or not visit.confirmation_expires_at
                or (visit.confirmation_expires_at.replace(tzinfo=UTC) if visit.confirmation_expires_at.tzinfo is None else visit.confirmation_expires_at) <= datetime.now(UTC)):
                raise HTTPException(status_code=409, detail="Контекст повтора изменился")
            check_bearer_expiry(bearer)
            result = InvitationReissueResponse(delivery_id=previous.id, state=previous.state, idempotent_replay=True)
            db.commit()
            return result
        if (patient.id != payload.expected_patient_id
            or patient.notification_owner_generation != payload.expected_owner_generation
            or visit.confirmation_context_epoch != payload.expected_context_epoch):
            raise HTTPException(status_code=409, detail="Контекст проверки устарел")
        token_parts = payload.token.split(".")
        now = int(datetime.now(UTC).timestamp())
        if (len(token_parts) != 2 or not re.fullmatch(r"[0-9]{1,12}", token_parts[0])
            or not re.fullmatch(r"[0-9a-f]{64}", token_parts[1])):
            raise HTTPException(status_code=409, detail="Контекст проверки устарел")
        expiry = int(token_parts[0])
        if expiry <= now or expiry > now + 300 or expiry > bearer.expires_at:
            raise HTTPException(status_code=409, detail="Контекст проверки устарел")
        _, snapshot = _reissue_review_snapshot(db, patient, visit)
        if not hmac.compare_digest(payload.token, _reissue_review_token(actor, bearer, snapshot, expiry)):
            raise HTTPException(status_code=409, detail="Контекст проверки устарел")
        visit.confirmation_channel = payload.channel
        db.flush()
        db.refresh(visit)
        visit.confirmation_token = secrets.token_urlsafe(32)
        visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=48)
        db.flush()
        db.refresh(visit)
        delivery_id = stage_visit_invitation(db, patient_id=patient.id, visit_id=visit.id,
            channel=payload.channel, issuer_actor_id=actor.id, issuer_key_digest=key_hash,
            issuer_fingerprint=fingerprint, require_deliverable=True, bearer=bearer,
            requester_type="admin", doctor_id=None, doctor_generation=None)
        if delivery_id is None:
            raise InvitationContextChanged("Delivery unavailable")
        _reissue_audit(db, actor, visit.id, "visit_invitation_reissued")
        check_bearer_expiry(bearer)
        db.commit()
        return InvitationReissueResponse(delivery_id=delivery_id, state="pending", idempotent_replay=False)
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен") from None
    except InvitationRuntimeUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Отправка временно недоступна") from None
    except (InvitationContextChanged, IntegrityError):
        db.rollback()
        raise HTTPException(status_code=409, detail="Не удалось подготовить приглашение") from None
    except FinancialFenceError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Визит сейчас недоступен") from None
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if code in {"40P01", "55P03"}:
            raise HTTPException(status_code=409, detail="Визит сейчас недоступен") from None
        raise HTTPException(status_code=500, detail="Не удалось подготовить приглашение") from None
    except ValueError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Некорректный Idempotency-Key") from None
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось подготовить приглашение") from None


router.include_router(_reissue_router)
