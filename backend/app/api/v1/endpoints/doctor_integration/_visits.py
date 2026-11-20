"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from doctor_integration.py (1900 LOC god file → modular).
"""

from __future__ import annotations

import hmac
from decimal import Decimal

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import oauth2_scheme
from app.api.trusted_financial_auth import _authenticate
from app.api.v1.endpoints.doctor_integration._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.doctor_integration._helpers import (  # noqa: F401
    DOCTOR_QUEUE_ALLOWED_TAGS,
    DOCTOR_QUEUE_SPECIALTY_VARIANTS,
    ScheduleNextVisitRequest,
    ScheduleNextVisitResponse,
    ScheduleNextVisitService,
    _doctor_queue_action_flags,
    _doctor_queue_available_actions,
    _doctor_schedule_patient_context_exists,
    _ensure_legacy_complete_doctor_access,
    _ensure_schedule_next_patient_access,
    _ensure_visit_doctor_access,
    _lock_schedule_next_patient_evidence,
    _normalize_queue_specialty,
    _probe_schedule_next_patient_evidence,
    _resolve_queue_allowed_tags,
    _resolve_queue_specialty_variants,
    _serialize_queue_doctor,
    _visit_filter_doctor_id,
    router,
)
from app.core.config import settings
from app.core.roles import normalize_role_value
from app.crud.clinic import clinic_today
from app.models.doctor_price_intent import DoctorPriceIntent, DoctorPriceIntentLine
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.appointment_duration_snapshot import (
    duration_snapshot_for_service_id,
)
from app.services.doctor_price_intent_service import (
    DoctorPriceIntentService,
    PriceIntentAmbiguous,
    PriceIntentConflict,
    PriceIntentInvalid,
    PriceIntentKeyring,
    PriceIntentPending,
    PriceIntentRetryable,
    PriceIntentUnavailable,
)
from app.services.doctor_repeat_discount import (
    RepeatPolicyError,
    prepare_repeat_discount,
)
from app.services.encounter_creation import create_standalone_encounter
from app.services.encounter_financial_fence import FinancialFenceError
from app.services.money_input import (
    MAX_MONEY,
    MoneyInputError,
    parse_exact_json,
    parse_money,
)
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
)
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_profile_bearer,
)
from app.services.visit_invitation_delivery import (
    InvitationContextChanged,
    stage_visit_invitation,
)

# DOCSCHED-BE-001..005 (audit #3892, group 18): the doctor schedule-next
# visit-creation plane. A repeated identical intent inside the dedup
# window replays the ORIGINAL visit/token instead of creating a second
# pending_confirmation visit; the all_free business field is canonical
# (visit, service rows, confirmation and billing agree); the past-date
# check follows the CLINIC's calendar (clinic_today SSOT), not the UTC
# host's date.today(); a non-doctor principal no longer writes its
# users.id into the doctors.id foreign key (unowned visit instead).

# DOCSCHED-BE-001: окно дедупликации повторного schedule-next intent'а.
# Покрывает повтор из-за потерянного HTTP-ответа/двойного нажатия;
# осознанная повторная запись пациента выполняется после истечения окна
# (или с другим intent'ом — время/услуги/скидка) и создаёт новый визит.
_SCHEDULE_NEXT_DEDUP_WINDOW_SECONDS = 10


def _acquire_schedule_next_dedup_lock(
    db: Session, *, patient_id: int, visit_date: date
) -> None:
    """DOCSCHED-BE-001: транзакционный PostgreSQL advisory-lock на intent
    (пациент + дата визита) — сериализует конкурирующие идентичные
    POST'ы между воркерами ДО check-before-write дедупликации (та же
    парадигма, что ``lock_owner_config_scope``/``acquire_phone_scope_lock``).
    SQLite (локальные тесты) advisory-локов не имеет — no-op.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"schedule_next:{patient_id}:{visit_date.isoformat()}"},
    )


def _schedule_next_service_lines_match(
    stored_lines: list[VisitService],
    intended: list[tuple[int, int, Decimal]],
) -> bool:
    """DOCSCHED-BE-001: строки услуг совпадают с intent'ом (multiset по
    (service_id, qty, effective price)). Prices are exact decimal amounts."""
    if len(stored_lines) != len(intended):
        return False
    stored = sorted(
        (line.service_id, line.qty or 0, Decimal(str(line.price or 0)))
        for line in stored_lines
    )
    wanted = sorted(
        (service_id, qty, price) for service_id, qty, price in intended
    )
    return stored == wanted


def _find_recent_identical_schedule_next(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int | None,
    visit_date: date,
    visit_time: str | None,
    discount_mode: str,
    notes: str | None,
    service_lines: list[tuple[int, int, Decimal]],
    confirmation_channel: str,
    ambiguous_catalog_price: bool = False,
) -> Visit | None:
    """DOCSCHED-BE-001: недавний идентичный pending_confirmation визит.

    Совпадение полного intent'а: пациент, врач (или его отсутствие), дата,
    время, каноничный discount_mode, заметки, все строки услуг с их
    эффективными ценами И канал подтверждения (RETRO-3960-01, пост-merge
    обзор #3968: канал — часть обещания операции; изменённый канал — другой
    intent, а не replay, иначе replay-ответ объявляет канал, который не
    хранится и по которому приглашение не отправлялось).
    Возвращённый визит — основа для replay-ответа; новый визит и токен
    подтверждения НЕ создаются.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=_SCHEDULE_NEXT_DEDUP_WINDOW_SECONDS)
    query = (
        db.query(Visit)
        .populate_existing()
        .filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == visit_date,
            Visit.status == "pending_confirmation",
            Visit.discount_mode == discount_mode,
            Visit.created_at >= cutoff,
        )
    )
    if doctor_id is None:
        query = query.filter(Visit.doctor_id.is_(None))
    else:
        query = query.filter(Visit.doctor_id == doctor_id)
    candidates = query.order_by(Visit.id.desc()).all()
    for candidate in candidates:
        if (candidate.visit_time or None) != (visit_time or None):
            continue
        if (candidate.notes or None) != (notes or None):
            continue
        # RETRO-3960-01: канал подтверждения — часть intent'а. Replay
        # возможен только для того же канала, что сохранён в визите, чтобы
        # confirmation.channel ответа всегда совпадал с persisted-каналом.
        if (candidate.confirmation_channel or None) != (confirmation_channel or None):
            continue
        stored_lines = (
            db.query(VisitService)
            .filter(VisitService.visit_id == candidate.id)
            .all()
        )
        if _schedule_next_service_lines_match(stored_lines, service_lines):
            return candidate
        if ambiguous_catalog_price and sorted(
            (line.service_id, line.qty or 0) for line in stored_lines
        ) == sorted((service_id, qty) for service_id, qty, _ in service_lines):
            # The original request's explicit-vs-catalog price choice is not
            # stored. If catalog price moved, we cannot safely infer whether
            # this is the retry of a lost response or a new appointment.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Цена каталога изменилась после похожего назначения. Проверьте существующий визит перед повтором.",
            )
    return None


def _schedule_next_confirmation_data(
    *,
    visit: Visit,
    patient: Patient,
    channel: str,
    total_amount: float,
    currency: str | None,
    services_count: int,
    notification_sent: bool,
) -> dict[str, Any]:
    """Единая сборка confirmation-блока ответа schedule-next (и для fresh,
    и для DOCSCHED-BE-001 replay-ответа из сохранённого визита)."""
    return {
        "token": visit.confirmation_token,
        "channel": channel,
        "expires_at": (
            visit.confirmation_expires_at.isoformat()
            if visit.confirmation_expires_at
            else None
        ),
        "patient_name": patient.short_name(),
        "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
        "visit_time": visit.visit_time,
        "total_amount": total_amount,
        "currency": currency,
        "services_count": services_count,
        "notification_sent": notification_sent,
    }

# DOCVISIT-BE-001/002/003 (audit #3892, group 17): the doctor-side
# visit-service mutation plane. The persisted ``VisitService.price`` IS the
# effective (custom or catalogue) price — there is no separate custom_price
# column, so responses must not fabricate one; inputs are validated before
# any persistence; and mutations coordinate with the payment ledger (the
# canonical Visit lock, in-flight invoice reservations and net settled
# amounts) instead of silently re-basing paid visits.


def _assert_visit_services_mutable(db: Session, visit_id: int) -> None:
    """DOCVISIT-BE-003: guard visit-service mutations against the payment
    ledger.

    Locks the visit row first (the same ``visits`` → invoice order payment
    flows use), rejects in-flight ``processing`` invoice reservations and
    fails closed when the visit has a net settled amount (paid minus
    completed refunds). Unpaid and fully refunded visits stay mutable.
    """
    invariant = PaymentInvariantService(db)
    invariant.lock_visit_for_payment_change(visit_id)
    net_settled = invariant.compute_paid_amount(visit_id)
    if net_settled > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Нельзя изменять услуги визита с проведённой оплатой "
                "(оплачено с учётом возвратов: "
                f"{net_settled}). Оформите возврат/пересчёт через кассу."
            ),
        )


_MAX_SERVICE_AMOUNT = MAX_MONEY
_MAX_SERVICE_QUANTITY = 2147483647  # PostgreSQL INTEGER


def _service_amount(value: Decimal | int | float) -> Decimal:
    """Reject amounts that cannot be represented exactly by the price column."""
    try:
        return parse_money(value)
    except MoneyInputError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Цена должна быть неотрицательной суммой с не более чем двумя знаками после запятой",
        ) from None


def _catalogue_currency(service: Service) -> str:
    currency = service.currency
    if (
        not isinstance(currency, str) or len(currency) != 3 or not currency.isascii()
        or not currency.isalpha() or not currency.isupper()
    ):
        raise HTTPException(status_code=409, detail="Валюта услуг требует сверки")
    return currency


def _validate_add_service_inputs(
    *, quantity: int, custom_price: Decimal | None
) -> None:
    """DOCVISIT-BE-002: quantity must be >= 1 and a custom price must be a
    finite non-negative amount. Rejected BEFORE any row is persisted."""
    if quantity < 1 or quantity > _MAX_SERVICE_QUANTITY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Количество услуги вне допустимого диапазона",
        )
    if custom_price is not None:
        _service_amount(custom_price)


def _find_recent_identical_add(
    db: Session,
    *,
    visit_id: int,
    service_id: int,
    quantity: int,
    effective_price,
) -> VisitService | None:
    """DOCVISIT-BE-001 retry-idempotency: the immediately preceding identical
    add (same service/quantity/effective price inside the short retry
    window) is treated as a replay of a lost HTTP response, not as a second
    clinical line."""
    cutoff = datetime.now(UTC) - timedelta(seconds=10)
    return (
        db.query(VisitService)
        .filter(
            VisitService.visit_id == visit_id,
            VisitService.service_id == service_id,
            VisitService.qty == quantity,
            VisitService.price == effective_price,
            VisitService.created_at >= cutoff,
        )
        .order_by(VisitService.id.desc())
        .first()
    )


_SCHEDULE_NEXT_ROLES = ("Admin", "Doctor", "Registrar", "Cashier", "cardio", "cardiology", "derma", "dentist")


async def _schedule_next_authenticated_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db),
) -> User:
    """Pin the deployment schema before the canonical JWT/RBAC database reads."""
    if db.get_bind().dialect.name == "postgresql":
        if (not settings.TRUSTED_DB_SCHEMA or not settings.TRUSTED_DB_SCHEMA_OWNER
            or not settings.TRUSTED_DB_RUNTIME_ROLE
            or settings.DOCTOR_PRICE_DB_SCHEMA != settings.TRUSTED_DB_SCHEMA
            or settings.INVITATION_DB_SCHEMA != settings.TRUSTED_DB_SCHEMA
            or settings.DOCTOR_PRICE_DB_SCHEMA_OWNER != settings.TRUSTED_DB_SCHEMA_OWNER
            or settings.INVITATION_DB_SCHEMA_OWNER != settings.TRUSTED_DB_SCHEMA_OWNER
            or settings.DOCTOR_PRICE_DB_RUNTIME_ROLE != settings.TRUSTED_DB_RUNTIME_ROLE):
            db.rollback()
            raise HTTPException(status_code=503, detail="Сервис записи временно недоступен")
    return await _authenticate(token, db, _SCHEDULE_NEXT_ROLES)


@router.post("/doctor/visits/schedule-next", response_model=ScheduleNextVisitResponse)
async def schedule_next_visit(
    request: ScheduleNextVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_schedule_next_authenticated_user),
    http_request: Request = None,
):
    """Create one server-priced visit and any row-bound pending requests atomically.

    A staged invitation is durable but is not dispatched here. The consumer
    and finance fences must be integrated before this slice is mergeable.
    """
    try:
        if http_request is None:
            raise HTTPException(status_code=401, detail="Сессия недействительна")
        try:
            payload = parse_exact_json(await http_request.body())
            request = ScheduleNextVisitRequest.model_validate(payload)
        except (ValueError, TypeError, ValidationError):
            raise HTTPException(status_code=422, detail="Некорректный формат запроса") from None
        for line in request.services:
            _validate_add_service_inputs(quantity=line.quantity, custom_price=line.custom_price)
        if request.discount_mode == "benefit":
            raise HTTPException(status_code=409, detail="Оформление льготы выполняется через регистратора")
        all_free = request.all_free or request.discount_mode == "all_free"
        discount_mode = "all_free" if all_free else request.discount_mode
        try:
            bearer = capture_profile_bearer(http_request, current_user)
        except ProfileBearerInvalid:
            raise HTTPException(status_code=401, detail="Сессия недействительна") from None
        if bearer.patient_id is not None:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        actor_id = current_user.id
        if db.get_bind().dialect.name == "postgresql" and (
            not settings.DOCTOR_PRICE_DB_SCHEMA or not settings.DOCTOR_PRICE_DB_SCHEMA_OWNER
            or settings.DOCTOR_PRICE_DB_SCHEMA != settings.INVITATION_DB_SCHEMA
            or settings.DOCTOR_PRICE_DB_SCHEMA_OWNER != settings.INVITATION_DB_SCHEMA_OWNER
        ):
            raise PriceIntentUnavailable("Doctor price and invitation schemas do not match")
        key = http_request.headers.get("Idempotency-Key")
        mode = http_request.headers.get("Idempotency-Intent")
        if mode is not None:
            mode = mode.strip().lower()
        canonical = {
            "patient_id": request.patient_id,
            "visit_date": request.visit_date.isoformat(),
            "visit_time": request.visit_time or None,
            "discount_mode": discount_mode,
            "notes": request.notes or None,
            "confirmation_channel": request.confirmation_channel,
            "services": sorted(
                ({"service_id": line.service_id, "quantity": line.quantity,
                  "custom_price_minor": None if line.custom_price is None else int(_service_amount(line.custom_price) * 100)}
                 for line in request.services),
                key=lambda item: item["service_id"],
            ),
        }
        if len({line.service_id for line in request.services}) != len(request.services):
            raise HTTPException(status_code=400, detail="Некоторые услуги не найдены")
        # Authentication dependencies may have opened a SQLite read snapshot.
        # It is safe to discard ONLY that clean dependency transaction; all
        # claims and roles are checked again after reserving the writer.
        if db.get_bind().dialect.name == "sqlite" and db.in_transaction():
            if db.new or db.dirty or db.deleted:
                raise HTTPException(status_code=409, detail="Незавершённые изменения запроса")
            db.rollback()
        keyring = PriceIntentKeyring.from_settings(settings)
        intents = DoctorPriceIntentService(db, keyring, settings.DOCTOR_PRICE_DB_SCHEMA, settings.DOCTOR_PRICE_DB_SCHEMA_OWNER, settings.DOCTOR_PRICE_DB_RUNTIME_ROLE)
        intents.reserve_sqlite_writer()
        intents.pin_trusted_schema()
        free_service = AllFreeRequestService(db) if all_free else None
        if free_service is not None:
            actor, auto_approve = free_service.lock_staging_inputs(bearer)
        else:
            actor = (db.query(User).filter(User.id == actor_id).with_for_update(nowait=True).populate_existing().first())
            if actor is None:
                raise ProfileBearerInvalid("Bearer session unavailable")
            check_profile_bearer(db, actor, bearer)
        role = normalize_role_value(actor.role)
        if not actor.is_active or (not actor.is_superuser and role not in {"admin", "doctor", "registrar", "cashier", "cardio", "cardiology", "derma", "dentist"}):
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        intents.lock_actor_scope(actor.id, "schedule_next")
        intents.verify_registry(register_active=True)
        result = intents.lookup(actor.id, "schedule_next", canonical, key, mode=mode)
        admin = staff_authorization_service.has_permission(actor, "users:manage")
        doctor = (db.query(Doctor).filter(Doctor.user_id == actor.id, Doctor.active.is_(True))
                  .with_for_update(nowait=True).populate_existing().first())
        if doctor is None and not admin:
            raise HTTPException(status_code=403, detail="Профиль врача недоступен")
        patient_query = db.query(Patient).filter(Patient.id == request.patient_id).populate_existing()
        if all_free:
            patient = patient_query.first() if lock_patient_subject(db, request.patient_id) else None
        else:
            patient = patient_query.with_for_update(nowait=True).first()
        if patient is None or patient.is_deleted:
            raise HTTPException(status_code=404, detail=t("patient.not_found"))

        if result.intent_id is not None:
            # Probe is not authority; each stored/live row is locked and
            # rechecked before returning data or binding a recovery key.
            probe = db.query(DoctorPriceIntent).filter(DoctorPriceIntent.id == result.intent_id).first()
            if probe is None or probe.visit_id is None:
                raise PriceIntentAmbiguous("Сохранённый результат требует сверки")
            visit = (db.query(Visit).filter(Visit.id == probe.visit_id)
                     .with_for_update(nowait=True).populate_existing().first())
            # The runtime role has SELECT/INSERT only on 0112 evidence.
            # Locked User/Patient/Visit/Doctor stabilize its live parent FKs;
            # child deletion is fenced below before the evidence is re-read.
            saved = (db.query(DoctorPriceIntent).filter(DoctorPriceIntent.id == result.intent_id)
                     .populate_existing().first())
            if (visit is None or saved is None or saved.actor_user_id != actor.id
                or saved.actor_user_id_snapshot != actor.id or saved.actor_user_auth_epoch != actor.auth_epoch
                or saved.patient_id != patient.id or saved.patient_id_snapshot != patient.id
                or saved.visit_id != visit.id or saved.visit_id_snapshot != visit.id
                or visit.patient_id != patient.id or (not admin and (doctor is None or visit.doctor_id != doctor.id))
                or (saved.doctor_id_snapshot is None and visit.doctor_id is not None)
                or (saved.doctor_id_snapshot is not None and (doctor is None or visit.doctor_id != saved.doctor_id_snapshot
                    or doctor.id != saved.doctor_id_snapshot or doctor.user_id != saved.doctor_owner_user_id
                    or doctor.price_owner_generation != saved.price_owner_generation))):
                raise PriceIntentAmbiguous("Сохранённый результат требует сверки")
            recorded = (db.query(DoctorPriceIntentLine).filter(DoctorPriceIntentLine.intent_id == saved.id)
                        .order_by(DoctorPriceIntentLine.ordinal).populate_existing().all())
            if len(recorded) != len(request.services) or any(row.visit_service_id is None for row in recorded):
                raise PriceIntentAmbiguous("Состав сохранённого результата изменился")
            ids = [row.visit_service_id for row in recorded]
            lines = (db.query(VisitService).filter(VisitService.id.in_(ids)).order_by(VisitService.id)
                     .with_for_update(nowait=True).populate_existing().all())
            # 0102 child writers lock child→Visit. NOWAIT avoids ABBA; once
            # child rows are held, refresh evidence after any concurrent FK
            # SET NULL instead of granting UPDATE to immutable intent tables.
            recorded = (db.query(DoctorPriceIntentLine).filter(DoctorPriceIntentLine.intent_id == saved.id)
                        .order_by(DoctorPriceIntentLine.ordinal).populate_existing().all())
            by_line_id = {line.id: line for line in lines}
            if (len(recorded) != len(ids) or len(lines) != len(ids) or any(
                record.visit_service_id != record.visit_service_id_snapshot
                or record.visit_service_id not in by_line_id
                or by_line_id[record.visit_service_id].visit_id != visit.id
                or by_line_id[record.visit_service_id].service_id != record.service_id_snapshot
                or by_line_id[record.visit_service_id].qty != record.qty
                for record in recorded
            )):
                raise PriceIntentAmbiguous("Состав сохранённого результата изменился")
            token_ok = False
            expires = visit.confirmation_expires_at
            if expires is not None and expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            saved_expiry = saved.issued_confirmation_expires_at
            if saved_expiry is not None and saved_expiry.tzinfo is None:
                saved_expiry = saved_expiry.replace(tzinfo=UTC)
            if (visit.status == "pending_confirmation" and visit.confirmation_token and expires is not None
                and expires > datetime.now(UTC) and saved_expiry == expires
                and saved.issued_confirmation_epoch == visit.confirmation_context_epoch
                and saved.issued_confirmation_digest is not None and saved.issued_confirmation_digest_version is not None):
                token_ok = hmac.compare_digest(
                    saved.issued_confirmation_digest,
                    intents.confirmation_digest(visit.confirmation_token, saved.issued_confirmation_digest_version)[1],
                )
            total = sum((_service_amount(line.price) * line.qty for line in lines), Decimal("0.00"))
            currencies = {line.currency for line in lines}
            currency = next(iter(currencies)) if len(currencies) == 1 else None
            data = _schedule_next_confirmation_data(visit=visit, patient=patient, channel=visit.confirmation_channel or request.confirmation_channel,
                                                   total_amount=float(total), currency=currency,
                                                   services_count=len(lines), notification_sent=False)
            if not token_ok:
                data["token"] = None
            if result.needs_alias:
                if key is None:
                    raise PriceIntentAmbiguous("Сохранённый результат требует сверки")
                intents.bind_alias(actor.id, "schedule_next", saved.id, key)
            if any((record.override_id_snapshot is None) != (record.override_id is None) for record in recorded):
                raise PriceIntentAmbiguous("История запроса цены изменилась")
            pending_ids = [record.override_id for record in recorded if record.override_id is not None]
            pending_rows = (db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id.in_(pending_ids))
                            .order_by(DoctorPriceOverride.id).with_for_update(nowait=True).populate_existing().all()) if pending_ids else []
            expected_targets = {record.override_id: record.visit_service_id for record in recorded if record.override_id is not None}
            if len(pending_rows) != len(pending_ids) or any(
                row.visit_id != visit.id or row.target_visit_service_id != expected_targets.get(row.id)
                or row.service_id != by_line_id[expected_targets[row.id]].service_id
                for row in pending_rows
            ):
                raise PriceIntentAmbiguous("История запроса цены изменилась")
            # Override deletion can null its FK without taking Visit. Once all
            # referenced overrides are locked, re-read the immutable evidence
            # and reject a deleted or rebound reference instead of replaying.
            recorded_again = (db.query(DoctorPriceIntentLine).filter(DoctorPriceIntentLine.intent_id == saved.id)
                              .order_by(DoctorPriceIntentLine.ordinal).populate_existing().all())
            if (len(recorded_again) != len(recorded) or any(
                record.override_id != record.override_id_snapshot for record in recorded_again
                if record.override_id_snapshot is not None
            )):
                raise PriceIntentAmbiguous("История запроса цены изменилась")
            pending_data = [{"id": row.id, "visit_service_id": row.target_visit_service_id, "status": row.status}
                            for row in pending_rows]
            response_visit_id, response_status = visit.id, visit.status
            check_bearer_expiry(bearer)
            db.commit()
            return ScheduleNextVisitResponse(success=True, message="Ранее созданный визит найден", visit_id=response_visit_id,
                                             status=response_status, confirmation=data, idempotent_replay=True,
                                             price_override_requests=pending_data)

        clinic_date = clinic_today(db)
        if request.visit_date < clinic_date:
            raise HTTPException(status_code=400, detail="Нельзя назначить визит на прошедшую дату")
        evidence = None if admin else _probe_schedule_next_patient_evidence(db, patient_id=patient.id, doctor=doctor)
        repeat = None
        if discount_mode == "repeat":
            try:
                repeat = prepare_repeat_discount(
                    db, patient_id=patient.id, doctor_id=doctor.id if doctor else None,
                    doctor_user_id=doctor.user_id if doctor else None, target_date=request.visit_date,
                    clinic_today=clinic_date,
                    additional_visit_ids=(evidence[1],) if evidence and evidence[0] == "visit" else (),
                )
            except RepeatPolicyError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if evidence:
            if repeat is not None and evidence[0] == "visit" and evidence[1] not in repeat.locked_visit_ids:
                raise HTTPException(status_code=409, detail="Назначение пациента изменилось")
            _lock_schedule_next_patient_evidence(db, patient_id=patient.id, doctor=doctor, candidate=evidence)
        service_ids = [line.service_id for line in request.services]
        services = (db.query(Service).filter(Service.id.in_(set(service_ids))).order_by(Service.id)
                    .with_for_update(nowait=True).populate_existing().all())
        by_id = {service.id: service for service in services}
        if len(by_id) != len(service_ids) or any(not item.active for item in services):
            raise HTTPException(status_code=400, detail="Некоторые услуги недоступны для новых назначений")
        currencies = {_catalogue_currency(service) for service in services}
        if len(currencies) != 1:
            raise HTTPException(status_code=409, detail="Валюта услуг требует сверки")
        currency, = currencies
        if repeat is not None:
            try:
                repeat.require_eligible(db, by_id, service_ids)
            except RepeatPolicyError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        prepared = []
        for line in request.services:
            service = by_id[line.service_id]
            if service.price is None:
                raise HTTPException(status_code=409, detail="Цена услуги в каталоге недоступна")
            catalog = _service_amount(service.price)
            raw = None if line.custom_price is None else _service_amount(line.custom_price)
            baseline = repeat.price(catalog, service.is_consultation) if repeat else catalog
            proposed_base = catalog if raw is None else raw
            proposed = repeat.price(proposed_base, service.is_consultation) if repeat else proposed_base
            if all_free and proposed != baseline:
                raise HTTPException(status_code=409, detail="Для заявки All Free используются обычные цены")
            if proposed != baseline and not admin and not service.allow_doctor_price_override:
                raise HTTPException(status_code=400, detail="Данная услуга не разрешает изменение цены врачом")
            prepared.append((service, line.quantity, raw, catalog, baseline, proposed))
        if any(sum((row[index] * row[1] for row in prepared), Decimal("0")) > _MAX_SERVICE_AMOUNT for index in (4, 5)):
            raise HTTPException(status_code=422, detail="Общая стоимость услуг превышает допустимую сумму")

        # Unknown old requests lack raw-price snapshots. A non-explicit new
        # intent cannot safely infer whether a similar legacy visit is a retry.
        if mode != "new":
            legacy = (db.query(Visit.id).filter(Visit.patient_id == patient.id,
                     Visit.doctor_id == (doctor.id if doctor else None), Visit.visit_date == request.visit_date,
                     Visit.visit_time == request.visit_time, Visit.discount_mode == discount_mode,
                     ~db.query(DoctorPriceIntent.id).filter(DoctorPriceIntent.visit_id == Visit.id).exists()).first())
            if legacy is not None:
                raise PriceIntentAmbiguous("Похожое назначение требует сверки")

        encounter = create_standalone_encounter(db, patient_id=patient.id)
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id if doctor else None, encounter_id=encounter.id,
                      visit_date=request.visit_date, visit_time=request.visit_time, status="pending_confirmation",
                      discount_mode=discount_mode, approval_status="pending" if all_free else "none",
                      department="mixed", notes=request.notes,
                      confirmation_channel=request.confirmation_channel, confirmation_token=None,
                      confirmation_expires_at=None, source="desk")
        db.add(visit)
        db.flush()
        staged_lines = []
        for service, qty, raw, catalog, baseline, proposed in prepared:
            item = VisitService(visit_id=visit.id, service_id=service.id, qty=qty, price=baseline,
                                duration_minutes_snapshot=duration_snapshot_for_service_id(db, service.id, doctor_id=visit.doctor_id),
                                name=service.name, code=service.service_code or get_service_code(service.id, db), currency=currency)
            db.add(item)
            staged_lines.append((item, service, qty, raw, catalog, baseline, proposed))
        db.flush()
        # SQLite AFTER triggers make INSERT RETURNING generations stale.
        db.refresh(visit)
        for item, *_ in staged_lines:
            db.refresh(item)
        if free_service is not None:
            free_request = free_service.stage_request(
                visit_id=visit.id, expected_epoch=visit.confirmation_context_epoch,
                bearer=bearer, require_financial_group=True,
            )
            if auto_approve:
                free_service._apply_unpublished_decision(
                    request_id=free_request.id, action="approve", bearer=bearer, decision_kind="policy",
                )
        token_digest = digest_version = issued_epoch = None
        if visit.approval_status != "pending":
            token = str(uuid.uuid4())
            visit.confirmation_token = token
            visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=48)
            db.flush()
            db.refresh(visit)
            issued_epoch = visit.confirmation_context_epoch
            digest_version, token_digest = intents.confirmation_digest(token)
        if doctor is not None:
            db.refresh(doctor)
        fingerprint_version, fingerprint = intents.fingerprint(canonical)
        saved = DoctorPriceIntent(operation="schedule_next", requester_type="admin" if admin else "doctor",
                    actor_user_id=actor.id, actor_user_id_snapshot=actor.id, actor_user_auth_epoch=actor.auth_epoch,
                    doctor_id=doctor.id if doctor else None, doctor_id_snapshot=doctor.id if doctor else None,
                    doctor_owner_user_id=doctor.user_id if doctor else None, doctor_owner_user_id_snapshot=doctor.user_id if doctor else None,
                    doctor_user_auth_epoch=actor.auth_epoch if doctor else None, price_owner_generation=doctor.price_owner_generation if doctor else None,
                    patient_id=patient.id, patient_id_snapshot=patient.id, visit_id=visit.id, visit_id_snapshot=visit.id,
                    fingerprint_version=fingerprint_version, fingerprint=fingerprint,
                    issued_confirmation_epoch=issued_epoch, issued_confirmation_digest=token_digest,
                    issued_confirmation_digest_version=digest_version, issued_confirmation_expires_at=visit.confirmation_expires_at)
        db.add(saved)
        db.flush()
        pending = []
        for ordinal, (item, service, qty, raw, catalog, baseline, proposed) in enumerate(staged_lines):
            override = None
            if proposed != baseline:
                override = DoctorPriceOverride(visit_id=visit.id, doctor_id=doctor.id if doctor else None, service_id=service.id,
                    target_scope="visit_service", target_visit_service_id=item.id,
                    visit_context_epoch=visit.confirmation_context_epoch, doctor_owner_user_id=doctor.user_id if doctor else None,
                    doctor_owner_generation=doctor.repeat_owner_generation if doctor else None,
                    price_context_generation=visit.price_context_generation, price_line_generation=item.price_line_generation,
                    price_owner_generation=doctor.price_owner_generation if doctor else None,
                    doctor_user_auth_epoch=actor.auth_epoch if doctor else None,
                    requester_type="admin" if admin else "doctor", requester_user_id=actor.id,
                    requester_user_id_snapshot=actor.id, requester_auth_epoch=actor.auth_epoch,
                    original_price=catalog, visit_price_before=baseline, new_price=proposed,
                    reason="Запрос врача" if not admin else "Запрос администратора", status="pending")
                db.add(override)
                db.flush()
                pending.append({"id": override.id, "visit_service_id": item.id, "status": "pending"})
            db.add(DoctorPriceIntentLine(intent_id=saved.id, ordinal=ordinal, service_id_snapshot=service.id, qty=qty,
                    raw_custom_minor=None if raw is None else int(raw * 100), baseline_minor=int(baseline * 100),
                    proposed_minor=int(proposed * 100), visit_service_id=item.id, visit_service_id_snapshot=item.id,
                    override_id=override.id if override else None, override_id_snapshot=override.id if override else None))
        db.flush()
        if key is not None:
            intents.bind_alias(actor.id, "schedule_next", saved.id, key)
        if visit.approval_status == "pending":
            message = "Заявка All Free ожидает решения администратора"
        else:
            # Durable stage only; no network dispatch from this producer.
            delivery_id = stage_visit_invitation(
                db, patient_id=patient.id, visit_id=visit.id, channel=request.confirmation_channel,
                bearer=bearer, requester_type="admin" if admin else "doctor",
                doctor_id=doctor.id if doctor else None,
                doctor_generation=doctor.price_owner_generation if doctor else None,
            )
            message = ("Визит назначен; приглашение ожидает отправки" if delivery_id is not None
                       else "Визит назначен; отправка приглашения недоступна")
        check_bearer_expiry(bearer)
        total = sum((_service_amount(item.price) * item.qty for item, *_ in staged_lines), Decimal("0.00"))
        response_data = _schedule_next_confirmation_data(visit=visit, patient=patient, channel=request.confirmation_channel,
                         total_amount=float(total),
                         currency=currency,
                         services_count=len(staged_lines), notification_sent=False)
        visit_id = visit.id
        db.commit()
        return ScheduleNextVisitResponse(success=True, message=message,
                     visit_id=visit_id, status="pending_confirmation", confirmation=response_data,
                     idempotent_replay=False, price_override_requests=pending)
    except HTTPException:
        db.rollback()
        raise
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сессия недействительна") from None
    except (AllFreeRequestError, PatientSubjectLockError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except FinancialFenceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except (PriceIntentPending, PriceIntentRetryable):
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "pending_outcome", "message": "Запрос ещё выполняется"}) from None
    except PriceIntentAmbiguous:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "ambiguous_retry", "message": "Проверьте прежнее назначение или начните новое с отдельным ключом"}) from None
    except PriceIntentConflict:
        db.rollback()
        raise HTTPException(status_code=409, detail="Запрос конфликтует с ранее сохранённым намерением") from None
    except PriceIntentInvalid:
        db.rollback()
        raise HTTPException(status_code=422, detail="Некорректный ключ или формат запроса") from None
    except PriceIntentUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="Сервис записи временно недоступен") from None
    except InvitationContextChanged:
        db.rollback()
        raise HTTPException(status_code=409, detail="Контекст приглашения изменился") from None
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
        if code == "55P03" or (isinstance(sqlite_code, int) and sqlite_code & 255 in (5, 6)):
            raise HTTPException(status_code=409, detail={"code": "pending_outcome", "message": "Контекст изменяется; повторите запрос"}) from None
        logger.error("Ошибка сохранения назначения (%s)", type(exc.orig).__name__)
        raise HTTPException(status_code=500, detail="Internal server error") from None
    except Exception as exc:
        db.rollback()
        logger.error("Ошибка назначения следующего визита (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Internal server error") from None

# ===================== УПРАВЛЕНИЕ ВИЗИТАМИ =====================


@router.get("/doctor/visits/today", response_model=dict[str, Any])
def get_today_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить сегодняшние визиты врача"""
    try:
        visits = crud_visit.get_today_visits_by_doctor(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
        )

        result = []
        for visit in visits:
            # Получаем услуги визита
            visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

            services_data = []
            total_amount = 0

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                service_data = {
                    "id": vs.id,
                    "service_id": vs.service_id,
                    "service_name": (
                        service.name if service else f"Услуга #{vs.service_id}"
                    ),
                    "quantity": vs.quantity,
                    "price": vs.price,
                    "total": vs.price * vs.quantity,
                }
                services_data.append(service_data)
                total_amount += service_data["total"]

            result.append(
                {
                    "id": visit.id,
                    "patient_id": visit.patient_id,
                    "visit_date": (
                        visit.visit_date.isoformat() if visit.visit_date else None
                    ),
                    "visit_time": visit.visit_time,
                    "status": visit.status,
                    "department": visit.department,
                    "discount_mode": visit.discount_mode,
                    "notes": visit.notes,
                    "services": services_data,
                    "total_amount": total_amount,
                    "created_at": (
                        visit.created_at.isoformat() if visit.created_at else None
                    ),
                }
            )

        return {"success": True, "visits": result, "total_count": len(result)}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/doctor/visits/statistics", response_model=dict[str, Any])
def get_visit_statistics(
    date_from: str | None = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: str | None = Query(
        None, description="Дата окончания в формате YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Получить статистику визитов врача"""
    try:
        from datetime import datetime

        date_from_obj = None
        date_to_obj = None

        if date_from:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()

        if date_to:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()

        stats = crud_visit.get_visit_statistics(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
            date_from=date_from_obj,
            date_to=date_to_obj,
        )

        return {
            "success": True,
            "statistics": stats,
            "period": {"date_from": date_from, "date_to": date_to},
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/doctor/visits/{visit_id}", response_model=dict[str, Any])
def get_visit_details(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить детали визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Получаем услуги визита
        visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

        services_data = []
        total_amount = 0

        for vs in visit_services:
            service = db.query(Service).filter(Service.id == vs.service_id).first()
            service_data = {
                "id": vs.id,
                "service_id": vs.service_id,
                "service_name": service.name if service else f"Услуга #{vs.service_id}",
                "service_code": (
                    (service.service_code or get_service_code(service.id, db))
                    if service
                    else None
                ),
                "quantity": vs.quantity,
                "price": vs.price,
                "total": vs.price * vs.quantity,
            }
            services_data.append(service_data)
            total_amount += service_data["total"]

        return {
            "success": True,
            "visit": {
                "id": visit.id,
                "patient_id": visit.patient_id,
                "doctor_id": visit.doctor_id,
                "visit_date": (
                    visit.visit_date.isoformat() if visit.visit_date else None
                ),
                "visit_time": visit.visit_time,
                "status": visit.status,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "approval_status": visit.approval_status,
                "notes": visit.notes,
                "services": services_data,
                "total_amount": total_amount,
                "created_at": (
                    visit.created_at.isoformat() if visit.created_at else None
                ),
                "confirmed_at": (
                    visit.confirmed_at.isoformat() if visit.confirmed_at else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/doctor/visits/{visit_id}/add-service", response_model=dict[str, Any])
def add_service_to_visit(
    visit_id: int,
    service_id: int,
    quantity: int = 1,
    custom_price: Decimal | None = Query(default=None, allow_inf_nan=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Добавить услугу к визиту.

    DOCVISIT-BE-002: ``quantity``/``custom_price`` валидируются ДО записи —
    некорректные строки не попадают в биллинг. DOCVISIT-BE-003: мутация
    координируется с платёжным легером (каноничный Visit-lock + отказ при
    processing-инвойсах и оплаченном остатке). DOCVISIT-BE-001: ответ
    строится ТОЛЬКО из персистентного состояния — ``price`` и есть
    фактическая цена (кастомная или каталожная), фантомного ``custom_price``
    поля не существует.
    """
    try:
        # DOCVISIT-BE-002: fail BEFORE any persistence.
        _validate_add_service_inputs(quantity=quantity, custom_price=custom_price)

        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Lock the visit first, as payment paths do, then lock and refresh the
        # catalog row. Both locks stay held until the line is committed.
        _assert_visit_services_mutable(db, visit_id)
        db.expire(visit, ["doctor"])
        _ensure_visit_doctor_access(visit, current_user)
        service = (
            db.query(Service).filter(Service.id == service_id)
            .with_for_update().populate_existing().first()
        )
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена"
            )
        if service.price is None:
            raise HTTPException(status_code=409, detail="Цена услуги в каталоге недоступна")
        catalogue_price = _service_amount(service.price)

        # DOCVISIT-BE-001 retry-idempotency: an exact repeat of the
        # immediately preceding add is a replay of a lost response, not a
        # second clinical line.
        effective_price = _service_amount(custom_price) if custom_price is not None else catalogue_price
        replayed = _find_recent_identical_add(
            db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            effective_price=effective_price,
        )
        if replayed is not None:
            return {
                "success": True,
                "message": "Услуга уже добавлена к визиту (повтор запроса)",
                "idempotent_replay": True,
                "visit_service": {
                    "id": replayed.id,
                    "service_id": replayed.service_id,
                    "service_name": service.name,
                    "quantity": replayed.quantity,
                    "price": replayed.price,
                    "total": replayed.price * replayed.quantity,
                },
            }

        if custom_price is None:
            cutoff = datetime.now(UTC) - timedelta(seconds=10)
            prior = (
                db.query(VisitService)
                .filter(
                    VisitService.visit_id == visit_id,
                    VisitService.service_id == service_id,
                    VisitService.qty == quantity,
                    VisitService.created_at >= cutoff,
                )
                .first()
            )
            if prior is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Цена каталога изменилась после похожего добавления. Проверьте услуги визита перед повтором.",
                )

        if not service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Услуга недоступна для новых назначений",
            )

        if effective_price != catalogue_price and not service.allow_doctor_price_override:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Данная услуга не разрешает изменение цены врачом",
            )
        currency = _catalogue_currency(service)
        existing_lines = db.query(VisitService.price, VisitService.qty, VisitService.currency).filter(
            VisitService.visit_id == visit_id
        ).all()
        if any(line.currency not in (None, currency) for line in existing_lines):
            raise HTTPException(status_code=409, detail="Валюта услуг требует сверки")
        if any(type(line.qty) is not int or not 1 <= line.qty <= _MAX_SERVICE_QUANTITY for line in existing_lines):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="В существующих услугах визита указано некорректное количество",
            )
        total_after_add = sum(
            (_service_amount(line.price or 0) * line.qty for line in existing_lines),
            effective_price * quantity,
        )
        if total_after_add > _MAX_SERVICE_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Общая стоимость услуг превышает допустимую сумму",
            )

        # Добавляем услугу
        visit_service = crud_visit.add_visit_service(
            db=db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            custom_price=effective_price,
            trusted_currency=currency,
        )

        return {
            "success": True,
            "message": "Услуга добавлена к визиту",
            "idempotent_replay": False,
            "visit_service": {
                "id": visit_service.id,
                "service_id": visit_service.service_id,
                "service_name": service.name,
                "quantity": visit_service.quantity,
                "price": visit_service.price,
                "total": visit_service.price * visit_service.quantity,
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/doctor/visits/{visit_id}/services/{visit_service_id}",
    response_model=dict[str, Any],
)
def remove_service_from_visit(
    visit_id: int,
    visit_service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Удалить услугу из визита.

    DOCVISIT-BE-003: удаление строки услуги оплаченного визита меняет базу
    стоимости под неизменным чеком — отказ (409), как и для добавления.
    """
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Удаляем услугу
        visit_service = (
            db.query(VisitService)
            .filter(
                VisitService.id == visit_service_id,
                VisitService.visit_id == visit.id,
            )
            .first()
        )

        if not visit_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга в визите не найдена",
            )

        # DOCVISIT-BE-003: coordinate with the payment ledger before the
        # destructive mutation.
        _assert_visit_services_mutable(db, visit_id)

        db.delete(visit_service)
        db.commit()

        return {"success": True, "message": "Услуга удалена из визита"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
