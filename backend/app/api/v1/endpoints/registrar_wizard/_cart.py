from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Any

from fastapi import Request
from sqlalchemy import tuple_
from sqlalchemy.exc import DBAPIError

from app.api.trusted_financial_auth import financial_admin, financial_reviewer
from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _apply_service_discount,
    _assert_cart_doctor_eligibility,
    _load_registration_discount_settings,
    _resolve_effective_discount_mode,
    _revalidate_cart_doctor_eligibility_locked,
)  # noqa: F401
from app.core.roles import normalize_role_value
from app.crud.clinic import clinic_today
from app.crud.queue_owner_policy import QueueOwnerConfigurationError
from app.models.all_free_request import AllFreeRequest
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.doctor_repeat_discount import (
    RepeatPolicyError,
    prepare_repeat_discount,
)
from app.services.encounter_creation import (
    EncounterCreationError,
    create_standalone_encounter,
    resolve_new_encounter,
)
from app.services.encounter_financial_fence import FinancialFenceError
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.price_override_approval import (
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
)
from app.services.registrar_doctor_eligibility import service_routes_to_resource_queue
from app.services.registrar_edit_delta_service import (
    partial_removal_targets,
    require_edit_delta_discount_mode,
)
from app.services.registrar_wizard_queue_assignment_service import (
    DuplicateCartResourceQueueVisitsError,
)


def _single_queue_ticket_price(
    assignments: list[dict[str, Any]],
    service_rows: list[tuple[VisitService, str | None]],
    invoice_visit_amount: Decimal,
) -> str | None:
    # Only stamp a price when the sole issued ticket unambiguously covers
    # every persisted line of this visit. Never attach the cart total, a
    # catalog price, or an inferred price for split/untagged services.
    if len(assignments) != 1 or not service_rows:
        return None
    assignment = assignments[0]
    queue_tag = assignment.get("queue_tag")
    if not queue_tag or not assignment.get("queue_id") or not assignment.get("number"):
        return None
    total = Decimal("0")
    for line, service_tag in service_rows:
        if service_tag != queue_tag or line.price is None or not line.qty:
            return None
        total += line.price * line.qty
    if total != invoice_visit_amount:
        return None
    return str(total)


def _issued_ticket_prices(
    db: Session,
    visit: Visit,
    assignments: list[dict[str, Any]],
    service_rows: list[tuple[VisitService, str | None]],
    invoice_visit_amount: Decimal,
) -> list[str] | None:
    # These rows come from the queue writer, not from the browser. Validate
    # the actual issued identities as well as the visit and patient binding.
    keys = [(assignment.get("queue_id"), assignment.get("number")) for assignment in assignments]
    if not keys or not service_rows or len(set(keys)) != len(keys):
        return None
    if any(not q or not n for q, n in keys):
        return None
    entries = db.query(
        OnlineQueueEntry.queue_id, OnlineQueueEntry.number, OnlineQueueEntry.services
    ).filter(
        OnlineQueueEntry.visit_id == visit.id,
        OnlineQueueEntry.patient_id == visit.patient_id,
        tuple_(OnlineQueueEntry.queue_id, OnlineQueueEntry.number).in_(keys),
    ).all()
    entry_services = {(entry.queue_id, entry.number): entry.services for entry in entries}
    if len(entries) != len(keys) or any(key not in entry_services for key in keys):
        return None

    line_counts: Counter[int] = Counter()
    line_amounts: dict[int, Decimal] = {}
    for line, _ in service_rows:
        if line.service_id is None or line.price is None or not line.qty:
            return None
        line_counts[line.service_id] += 1
        line_amounts[line.service_id] = (
            line_amounts.get(line.service_id, Decimal("0")) + line.price * line.qty
        )
    if sum(line_amounts.values(), Decimal("0")) != invoice_visit_amount:
        return None

    assigned_counts: Counter[int] = Counter()
    amounts = []
    for key in keys:
        identified_services = entry_services[key]
        if not isinstance(identified_services, list) or not identified_services:
            return None
        ids = set()
        for ticket_line in identified_services:
            service_id = ticket_line.get("id") if isinstance(ticket_line, dict) else None
            if type(service_id) is not int or service_id not in line_amounts:
                return None
            assigned_counts[service_id] += 1
            if service_id in ids or assigned_counts[service_id] != 1:
                # Without persisted line ids, repeated service ids cannot be
                # allocated across entries, even if amounts happen to match.
                return None
            ids.add(service_id)
        amounts.append(str(sum((line_amounts[service_id] for service_id in ids), Decimal("0"))))
    if assigned_counts != line_counts:
        return None
    return amounts


def _attach_issued_ticket_prices(
    db: Session, invoice_id: int, visits: list[Visit], queue_numbers: dict[int, list[dict]],
) -> None:
    if not queue_numbers:
        return
    # The provisional registrar total is intentionally preserved for the
    # All Free audit baseline. Use the final, transaction-local allocation.
    amounts: dict[int, list[Decimal]] = {}
    for visit_id, amount in (
        db.query(PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.visit_amount)
        .filter(
            PaymentInvoiceVisit.invoice_id == invoice_id,
            PaymentInvoiceVisit.visit_id.in_(queue_numbers),
        )
        .all()
    ):
        amounts.setdefault(visit_id, []).append(amount)

    for visit in visits:
        assignments = queue_numbers.get(visit.id, [])
        allocated = amounts.get(visit.id, [])
        if not assignments or len(allocated) != 1:
            continue
        rows = (
            db.query(VisitService, Service.queue_tag)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(VisitService.visit_id == visit.id)
            .all()
        )
        total = allocated[0]
        prices = _issued_ticket_prices(db, visit, assignments, rows, total)
        if prices is None:
            single = _single_queue_ticket_price(assignments, rows, total)
            if single is not None:
                prices = [single]
        if prices is not None:
            queue_numbers[visit.id] = [
                {**assignment, "service_price": price}
                for assignment, price in zip(assignments, prices, strict=True)
            ]


@router.post("/registrar/cart", response_model=CartResponse)
def create_cart_appointments(
    cart_data: CartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    http_request: Request = None,
):
    """
    Создание корзины визитов с единым платежом
    Поддерживает: повторные/льготные визиты, All Free, динамические цены, очереди по queue_tag
    """
    effective_discount_mode = _resolve_effective_discount_mode(cart_data)
    if str(effective_discount_mode).strip().casefold() == "benefit":
        raise HTTPException(status_code=409, detail="Для льготы требуется подтверждение администратора")

    all_free_service = (
        AllFreeRequestService(db) if effective_discount_mode == "all_free" else None
    )
    all_free_bearer = None
    auto_approve = False

    logger.info(
        "REGISTRATION: Получен запрос на создание корзины. Patient ID: %s, Визитов: %d, Discount mode: %s, Effective discount mode: %s, All free: %s, Payment method: %s",
        cart_data.patient_id,
        len(cart_data.visits),
        cart_data.discount_mode,
        effective_discount_mode,
        cart_data.all_free,
        cart_data.payment_method,
    )

    try:
        if all_free_service is not None:
            if http_request is None:
                raise ProfileBearerInvalid("Bearer session unavailable")
            require_patient_subject_visibility(db)
            all_free_bearer = capture_profile_bearer(http_request, current_user)
            actor, auto_approve = all_free_service.lock_staging_inputs(all_free_bearer)
            require_roles("Admin", "Registrar")(current_user=actor, db=db)

        if db.get_bind().dialect.name == "sqlite":
            # SQLite SELECT and FOR UPDATE do not reserve a writer. Reserve
            # before any catalog/doctor read for every cart mode, otherwise
            # a concurrent change can commit after quote validation.
            try:
                if not lock_patient_subject(db, cart_data.patient_id):
                    raise HTTPException(status_code=404, detail="Пациент не найден")
            except PatientSubjectLockError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
        # RQ-05.a (server-side doctor eligibility): requires_doctor=true
        # услуги не должны сохраняться без врача, с неактивным врачом или
        # врачом чужой специальности (E-023: на пути корзины проверки НЕ
        # было). Гейт стоит ДО prelock advisory-замков и первой записи:
        # отклонённая корзина не оставляет частичного состояния. Семантика
        # специальности зеркалирует фронтовый filterDoctorsForService
        # (SSOT: DOCTOR_QUEUE_SPECIALTY_VARIANTS).
        _assert_cart_doctor_eligibility(db, cart_data.visits)
        requested_ids = sorted({item.service_id for visit in cart_data.visits for item in visit.services})
        routing_before = {
            service.id: (service.queue_tag, service.department_key, service.requires_doctor,
                         service.is_consultation, service.doctor_id)
            for service in db.query(Service).filter(Service.id.in_(requested_ids)).all()
        }

        # QD-2E review P1 (cart/GQL lock ordering): every (day, tag) claim
        # scope of the cart is taken BEFORE the first cart write. The
        # visit INSERTs below fire the doctors FK check — a FOR KEY SHARE
        # row lock on the doctor held until the single db.commit() below —
        # so acquiring the tag/day advisory locks only inside queue
        # assignment inverted the order against GraphQL joinQueue (tag
        # lock first, then Doctor FOR UPDATE) and deadlocked PostgreSQL
        # under concurrency. Pre-acquired scopes are re-entrant inside the
        # assignment pass (idempotent transaction-scoped xact locks).
        # Capture the clinic calendar day once for validation, locking and
        # assignment, even if the clinic and host cross midnight separately.
        today = clinic_today(db)
        RegistrarWizardQueueAssignmentService.assert_unique_same_day_resource_queue_visits(
            db,
            cart_data.visits,
            target_day=today,
        )
        RegistrarWizardQueueAssignmentService.prelock_cart_tag_claim_scopes(
            db,
            cart_data.visits,
            target_day=today,
        )

        # PR #3438 review P1-2 (+ round-2 P1): revalidate doctor eligibility
        # ON THE LOCKED snapshot, after the (day, tag) prelocks and BEFORE
        # the first visit INSERT. The unlocked gate above can race a
        # concurrent admin deactivation/demotion that commits between the
        # check and this cart's single commit — the cart would then create
        # a new visit and queue entry for an ineligible doctor. The locked
        # re-read keeps the global lock order (tag prelocks -> User FOR
        # SHARE -> Doctor FOR SHARE; users-first mirrors update_user's
        # lock_user_candidate_state -> _sync_doctor_active) and holds the
        # row locks until the commit below, so an eligibility-changing
        # UPDATE either blocks (revalidated snapshot stays valid) or is
        # already visible here (cart rejected before any write).
        _revalidate_cart_doctor_eligibility_locked(db, cart_data.visits)
        if all_free_service is not None and db.get_bind().dialect.name != "sqlite":
            if not lock_patient_subject(db, cart_data.patient_id):
                raise HTTPException(status_code=404, detail="Пациент не найден")

        # Lock historical evidence before catalog rows, like the doctor
        # scheduling path. A preview never authorizes a repeat price.
        repeat_snapshots: dict[int, Any] = {}
        if effective_discount_mode == "repeat":
            try:
                if db.get_bind().dialect.name != "sqlite" and not lock_patient_subject(db, cart_data.patient_id):
                    raise HTTPException(status_code=404, detail="Пациент не найден")
                # SQLite's FOR SHARE is a no-op; reread the doctor linkage
                # after reserving its writer through the Patient capability.
                _revalidate_cart_doctor_eligibility_locked(db, cart_data.visits)
                clinic_date = crud_clinic.clinic_today(db)
                for index, requested in enumerate(cart_data.visits):
                    if requested.doctor_id is None:
                        continue
                    doctor = db.query(Doctor).filter(Doctor.id == requested.doctor_id).populate_existing().first()
                    repeat_snapshots[index] = prepare_repeat_discount(
                        db, patient_id=cart_data.patient_id,
                        doctor_id=doctor.id if doctor else None,
                        doctor_user_id=doctor.user_id if doctor else None,
                        target_date=requested.visit_date, clinic_today=clinic_date,
                    )
            except PatientSubjectLockError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
            except RepeatPolicyError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from None

        # Lock settings and catalog in a deterministic order before quote
        # revalidation. NOWAIT prevents holding historical Visit locks while
        # waiting for a catalog writer that may itself need those visits.
        initial_settings = _load_registration_discount_settings(db, lock_rows=True)
        services = (
            db.query(Service).filter(Service.id.in_(requested_ids)).order_by(Service.id)
            .with_for_update(nowait=True).populate_existing().all()
        ) if requested_ids else []
        validated_settings = _assert_quote_token_matches(
            db,
            items=[CartQuoteItemRequest(service_id=item.service_id, quantity=item.quantity,
                                        custom_price=item.custom_price)
                   for visit in cart_data.visits for item in visit.services],
            discount_mode=cart_data.discount_mode, all_free=cart_data.all_free,
            pricing_mode="cart", quote_token=cart_data.quote_token,
            locked_settings=initial_settings,
        ) if cart_data.quote_token else None
        registration_settings = validated_settings or initial_settings
        service_map = {service.id: service for service in services}
        if not requested_ids or len(service_map) != len(requested_ids):
            raise HTTPException(status_code=404, detail="Некоторые услуги недоступны")
        if any(routing_before.get(service.id) != (
                service.queue_tag, service.department_key, service.requires_doctor,
                service.is_consultation, service.doctor_id) for service in services):
            raise HTTPException(status_code=409, detail="Маршрутизация услуги изменилась, повторите оформление")
        _assert_cart_doctor_eligibility(db, cart_data.visits)

        currencies: dict[int, str] = {}
        for service in services:
            currency = service.currency
            if (not service.active or service.price is None or not Decimal(str(service.price)).is_finite()
                    or Decimal(str(service.price)) < 0 or not isinstance(currency, str)
                    or len(currency) != 3 or not currency.isascii() or not currency.isalpha()
                    or currency != currency.upper()):
                raise HTTPException(status_code=409, detail="Цена или валюта услуги недоступна")
            currencies[service.id] = currency
        if len(set(currencies.values())) != 1:
            raise HTTPException(status_code=409, detail="Услуги с разными валютами нельзя объединить в один счёт")
        invoice_currency = next(iter(currencies.values()))
        for index, requested in enumerate(cart_data.visits):
            if any(item.custom_price is not None and item.custom_price != service_map[item.service_id].price
                   for item in requested.services):
                # Until the transactional approval producer is wired, never
                # turn an unreviewed caller price into an approved invoice.
                raise HTTPException(status_code=409, detail="Изменение цены требует согласования")
            if effective_discount_mode != "repeat":
                continue
            consultation_ids = [item.service_id for item in requested.services
                                if service_map[item.service_id].is_consultation]
            if consultation_ids:
                snapshot = repeat_snapshots.get(index)
                if snapshot is None:
                    raise HTTPException(status_code=409, detail="Повторный визит требует назначенного врача")
                try:
                    snapshot.require_eligible(db, service_map, consultation_ids)
                except RepeatPolicyError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from None
                if snapshot.percentage != Decimal(str(registration_settings["repeat_visit_discount"])):
                    raise HTTPException(status_code=409, detail="Настройки повторного визита изменились")

        # Reject values that the persisted Numeric(12,2) or int32 quantities
        # cannot represent before creating an encounter or any visit.
        prepared_prices: dict[int, list[Decimal]] = {}
        prepared_amounts: dict[int, Decimal] = {}
        maximum_amount = Decimal("9999999999.99")
        with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
            invoice_amount = Decimal("0")
            for index, requested in enumerate(cart_data.visits):
                amounts: list[Decimal] = []
                visit_total = Decimal("0")
                for item in requested.services:
                    if item.quantity > 2147483647:
                        raise HTTPException(status_code=422, detail="Количество услуги превышает допустимое значение")
                    service = service_map[item.service_id]
                    base_price = Decimal(str(item.custom_price if item.custom_price is not None else service.price))
                    snapshot = repeat_snapshots.get(index)
                    if all_free_service is not None:
                        # Persist the ordinary price before applying any approved reduction.
                        price = base_price
                    elif snapshot is not None:
                        price = snapshot.price(base_price, service.is_consultation)
                    else:
                        price = _apply_service_discount(
                            base_price, effective_discount_mode, registration_settings,
                            service.is_consultation,
                        )
                    visit_total += price * item.quantity
                    amounts.append(price)
                if visit_total > maximum_amount:
                    raise HTTPException(status_code=422, detail="Стоимость визита превышает допустимое значение")
                invoice_amount += visit_total
                prepared_prices[index], prepared_amounts[index] = amounts, visit_total
            if invoice_amount > maximum_amount:
                raise HTTPException(status_code=422, detail="Стоимость оформления превышает допустимое значение")

        # A registration is one encounter, independently of visit dates or
        # doctors. The marker prevents joining an already committed group.
        cart_transaction = db.get_transaction()
        try:
            encounter = (
                create_standalone_encounter(db, patient_id=cart_data.patient_id)
                if cart_data.visits else None
            )
        except EncounterCreationError as exc:
            raise HTTPException(status_code=404, detail="Пациент не найден") from exc

        created_visits = []
        created_visit_amounts: dict[int, Decimal] = {}
        total_invoice_amount = invoice_amount

        # Создаём визиты
        from time import sleep

        logger.info("REGISTRATION: Создаём %d визитов", len(cart_data.visits))
        for idx, visit_req in enumerate(cart_data.visits):
            logger.debug(
                "REGISTRATION: Визит %d: department=%s, services=%d",
                idx + 1,
                visit_req.department,
                len(visit_req.services),
            )
            visit_status = "pending_confirmation" if all_free_service else "confirmed"
            confirmed_at = None if all_free_service else datetime.now(UTC)
            confirmed_by = None if all_free_service else f"registrar_{current_user.id}"

            # [OK] ИСПРАВЛЕНО: Добавляем микрозадержку для разных created_at
            # Это гарантирует, что визиты одного пациента будут иметь разные временные метки
            if idx > 0:
                sleep(0.001)  # 1 миллисекунда задержки между визитами

            # Подготавливаем услуги для передачи в create_visit
            services_data = []
            visit_amount = prepared_amounts[idx]
            for service_index, service_item in enumerate(visit_req.services):
                service = service_map[service_item.service_id]
                item_price = prepared_prices[idx][service_index]

                services_data.append(
                    {
                        "service_id": service.id,
                        # ⭐ SSOT: используем canonical service_code helper
                        "code": service.service_code or get_service_code(service.id, db),
                        "name": service.name,
                        "qty": service_item.quantity,
                        "price": item_price,
                    }
                )

            # Создаём визит используя единую функцию create_visit для обеспечения Single Source of Truth
            from app.crud.visit import create_visit

            visit = create_visit(
                db=db,
                patient_id=cart_data.patient_id,
                encounter_id=encounter.id if encounter is not None else None,
                doctor_id=visit_req.doctor_id,
                visit_date=visit_req.visit_date,
                visit_time=visit_req.visit_time,
                department=visit_req.department,
                notes=visit_req.notes,
                discount_mode=effective_discount_mode,
                services=services_data,
                trusted_currency_by_service={item.service_id: currencies[item.service_id] for item in visit_req.services},
                status=visit_status,
                approval_status="pending" if all_free_service else "approved",
                confirmed_at=confirmed_at,
                confirmed_by=confirmed_by,
                auto_status=False,  # Статус уже установлен выше
                notify=False,  # Уведомления отправляются отдельно
                log=True,
                # Fix C (cart atomicity): все визиты корзины, invoice,
                # invoice-visit связи и записи очереди коммитятся ОДНОЙ
                # транзакцией ниже (db.commit() после queue assignment).
                # Раньше create_visit() коммитил каждый визит отдельно, и
                # сбой на позднем визите/invoice оставлял частичные данные.
                commit=False,
            )
            logger.info("REGISTRATION: Визит %d создан через create_visit()", visit.id)

            created_visits.append(visit)
            created_visit_amounts[visit.id] = visit_amount

        all_free_requests = []
        if all_free_service is not None:
            # The complete membership and service lines must be visible before
            # freezing their generations. Stage before adding invoice links.
            db.flush()
            for visit in created_visits:
                db.refresh(visit)
                free_request = all_free_service.stage_request(
                    visit_id=visit.id,
                    expected_epoch=visit.confirmation_context_epoch,
                    bearer=all_free_bearer,
                    require_financial_group=True,
                )
                if free_request.baseline_total != created_visit_amounts[visit.id]:
                    raise AllFreeRequestError(409, "Обычные цены заявки требуют сверки")
                all_free_requests.append(free_request)
            logger.info(
                "REGISTRATION: Визит %d создан успешно для пациента %d",
                visit.id,
                cart_data.patient_id,
            )

        # Создаём единый invoice
        logger.info("REGISTRATION: Создаём инвойс на сумму %s", total_invoice_amount)
        if encounter is not None:
            # Read the generation after all Visit membership triggers ran.
            db.refresh(encounter, attribute_names=["generation"])
        invoice = PaymentInvoice(
            patient_id=cart_data.patient_id,
            registrar_encounter_id_snapshot=encounter.id if encounter is not None else None,
            registrar_encounter_generation_snapshot=encounter.generation if encounter is not None else None,
            total_amount=total_invoice_amount,
            currency=invoice_currency,
            status="pending",
            payment_method=cart_data.payment_method,
            notes=cart_data.notes,
        )
        db.add(invoice)
        db.flush()  # Получаем ID invoice
        logger.info("REGISTRATION: Инвойс %d создан", invoice.id)

        # Связываем визиты с invoice
        for visit in created_visits:
            visit_amount = created_visit_amounts.get(visit.id, Decimal("0"))
            invoice_visit = PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=visit.id, visit_amount=visit_amount
            )
            db.add(invoice_visit)

        if all_free_service is not None and auto_approve:
            db.flush()
            for free_request in all_free_requests:
                all_free_service._apply_unpublished_decision(
                    request_id=free_request.id,
                    action="approve",
                    bearer=all_free_bearer,
                    decision_kind="policy",
                )
            total_invoice_amount = invoice.total_amount
            confirmed_at = datetime.now(UTC)
            for visit in created_visits:
                visit.status = "confirmed"
                visit.confirmed_at = confirmed_at
                visit.confirmed_by = f"registrar_{current_user.id}"

        # Assign queue entries for confirmed same-day visits via extracted seam.
        queue_numbers = {}
        # ``today`` was computed BEFORE the pre-lock above — the same
        # instance is reused so the assignment pass targets exactly the
        # scopes that were pre-acquired.

        queue_numbers = RegistrarWizardQueueAssignmentService(db).assign_same_day_queue_numbers(
            created_visits,
            target_day=today,
            source="desk",
            current_user=current_user,
        )

        if db.get_transaction() is not cart_transaction:
            raise RuntimeError("Cart transaction ended during queue assignment")
        if encounter is not None:
            current_encounter = resolve_new_encounter(
                db, patient_id=cart_data.patient_id, encounter_id=encounter.id
            )
            if (invoice.registrar_encounter_id_snapshot, invoice.registrar_encounter_generation_snapshot) != (
                current_encounter.id, current_encounter.generation,
            ):
                raise FinancialFenceError("Состав оформления изменился")
            if db.get_bind().dialect.name == "sqlite":
                # PostgreSQL validates these links again with a deferred constraint trigger.
                links = (db.query(PaymentInvoiceVisit.visit_id).filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                         .order_by(PaymentInvoiceVisit.visit_id).all())
                if [link.visit_id for link in links] != sorted(visit.id for visit in created_visits):
                    raise FinancialFenceError("Состав счёта изменился")

        _attach_issued_ticket_prices(db, invoice.id, created_visits, queue_numbers)
        if all_free_bearer is not None:
            check_bearer_expiry(all_free_bearer)
        db.commit()
        logger.info("REGISTRATION: Транзакция зафиксирована в базе данных")

        if effective_discount_mode == "all_free":
            for visit in created_visits:
                if visit.approval_status != "pending":
                    continue
                try:
                    asyncio.run(
                        notification_sender_service.send_all_free_request_notification(
                            db=db,
                            visit=visit,
                            actor_user=current_user,
                        )
                    )
                except Exception as notification_error:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] failed to publish all_free_requested after cart commit",
                        extra={
                            "visit_id": visit.id,
                            "patient_id": cart_data.patient_id,
                            "actor_id": current_user.id,
                            "error": str(notification_error),
                        },
                    )

        # Формируем талоны для визитов с присвоенными номерами очередей
        print_tickets = []
        # Блок формирования талонов пропускаем, так как queue_numbers пустой

        # Формируем информацию о созданных визитах
        created_visits_info = []
        try:
            for visit in created_visits:
                # Получаем данные пациента
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                patient_name = (
                    patient.short_name() if patient else "Неизвестный пациент"
                )

                # Получаем данные врача
                doctor = (
                    db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    if visit.doctor_id
                    else None
                )
                # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                if doctor and doctor.user_id:
                    user = db.query(User).filter(User.id == doctor.user_id).first()
                    doctor_name = (
                        (user.full_name or user.username) if user else "Без врача"
                    )
                else:
                    doctor_name = "Без врача"

                # Получаем услуги визита
                visit_services = (
                    db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                services_info = []
                for vs in visit_services:
                    services_info.append(
                        {
                            "name": vs.name,
                            "code": (
                                normalize_service_code(vs.code) if vs.code else None
                            ),
                            "quantity": vs.qty,
                            "price": float(vs.price) if vs.price else 0,
                        }
                    )

                confirmation_available = (
                    visit.status == "pending_confirmation"
                    and visit.approval_status != "pending"
                    and bool(visit.confirmation_token)
                )
                created_visits_info.append(
                    {
                        "visit_id": visit.id,
                        "patient_name": patient_name,
                        "doctor_name": doctor_name,
                        "visit_date": visit.visit_date.isoformat(),
                        "visit_time": visit.visit_time,
                        "status": visit.status,
                        "approval_status": visit.approval_status,
                        "department": visit.department,
                        "services": services_info,
                        "confirmation_required": confirmation_available,
                        "confirmation_token": (
                            visit.confirmation_token if confirmation_available else None
                        ),
                    }
                )
        except Exception as e:
            logger.warning(
                "REGISTRATION: Ошибка формирования ответа (визиты уже сохранены): %s",
                str(e),
                exc_info=True,
            )
            # Визиты уже сохранены, поэтому не откатываем транзакцию

        # Определяем сообщение в зависимости от результата
        if all_free_service is not None and not auto_approve:
            message = ALL_FREE_DECISION_REQUIRED
        elif queue_numbers:
            message = f"Корзина создана успешно. Присвоено номеров в очередях: {sum(len(assignments) for assignments in queue_numbers.values())}"
        else:
            message = "Визиты созданы. Номера в очередях будут присвоены в день визита."

        logger.info(
            "REGISTRATION: Корзина создана успешно. Создано визитов: %d, ID визитов: %s, Invoice ID: %d, Total amount: %s",
            len(created_visits),
            [v.id for v in created_visits],
            invoice.id,
            total_invoice_amount,
        )

        return CartResponse(
            success=True,
            message=message,
            invoice_id=invoice.id,
            visit_ids=[v.id for v in created_visits],
            total_amount=total_invoice_amount,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
            created_visits=created_visits_info,
        )

    except HTTPException:
        # Fix C (cart atomicity): ветка HTTPException (404 услуга и т.п.)
        # раньше делала raise без rollback — при внутренних коммитах
        # create_visit это было неважно, но с единой транзакцией любой
        # путь ошибки обязан откатить частичные данные корзины.
        db.rollback()
        raise
    except (AllFreeRequestError, PatientSubjectLockError) as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    except FinancialFenceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сессия недоступна") from None
    except DuplicateCartResourceQueueVisitsError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except QueueOwnerConfigurationError as exc:
        # QD-2E (RQ-15.b): fail-closed владелец очереди — это
        # КОНФИГУРАЦИОННАЯ ошибка каталога (D-08), а не сбой сервера:
        # откатываем корзину и возвращаем оператору 422 с причиной и
        # тремя путями решения (assign_doctor / retag_resource /
        # disable_service по operator map RQ-15.b).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        sqlite_code = getattr(exc.orig, "sqlite_errorcode", None)
        if code in {"55P03", "40P01", "40001"} or (sqlite_code is not None and sqlite_code & 0xff in {5, 6}):
            raise HTTPException(status_code=409, detail="Оформление занято, повторите запрос") from None
        raise HTTPException(status_code=500, detail="Ошибка создания корзины") from None
    except Exception as e:
        logger.exception(
            "REGISTRATION: cart creation failed",
            extra={"error_class": e.__class__.__name__},
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка создания корзины",
        )


# ===================== УПРАВЛЕНИЕ ИЗМЕНЕНИЯМИ ЦЕН =====================


def _quote_token(items: list[CartQuoteItemResponse], total_amount: Decimal, approval_status: str, quote_req: CartQuoteRequest, currency: str | None) -> str:
    """Canonical binding token of a computed quote (Codex R3 #3095 P1).

    sha256 over the ORDER-INSENSITIVE multiset of priced items (same items in
    a different visit grouping produce the same token) plus the pricing
    context. A later change of catalog prices or discount settings changes
    the recomputed token, so a stale confirmed quote is detectable at save
    time instead of silently invoicing a different amount.
    """
    canonical_items = sorted(
        (
            {
                "service_id": int(item.service_id),
                "quantity": int(item.quantity),
                "unit_price": str(item.unit_price),
                "discount_percent": int(item.discount_percent),
                "final_price": str(item.final_price),
            }
            for item in items
        ),
        key=lambda d: (d["service_id"], d["quantity"], d["unit_price"], d["final_price"]),
    )
    # Codex R7 #3095 (P1): токен биндит РЕЗОЛВНУТЫЙ режим (SSOT-резолв
    # пары all_free + discount_mode), а не сырые поля запроса — иначе
    # одно и то же подтверждённое ценообразование, выраженное булевым
    # флагом или строковым режимом, давало бы разные токены, и
    # нормализация режима на сохранении роняла ревалидацию в 409.
    _effective_mode = _resolve_effective_discount_mode(quote_req)
    payload = {
        "pricing_mode": quote_req.pricing_mode,
        "discount_mode": _effective_mode,
        "all_free": _effective_mode == "all_free",
        "approval_status": approval_status,
        "items": canonical_items,
        "total_amount": str(total_amount),
        "currency": currency,
    }
    if any(item.quantity == 0 for item in quote_req.items):
        payload["partial_removals"] = sorted(
            (item.queue_entry_id, item.service_id)
            for item in quote_req.items if item.quantity == 0
        )
        payload["patient_id"] = quote_req.patient_id
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _edit_delta_quote_context(
    db: Session,
    *,
    service: Service,
    requested_qty: int,
    patient_id: int,
    target_date: date,
    preferred_entry_ids: set[int],
    specialist_id: int | None = None,
    queue_entry_id: int | None = None,
    lock: bool = False,
    all_free: bool = False,
    removal_service_ids: set[int] | None = None,
) -> tuple[int, Decimal | None]:
    """Codex R6 #3095 (P2): mirror the edit-delta command's billing quantity.

    W2-PR1: the command bills the SIGNED target-state delta
    (requested − existing): increases bill the remainder, decreases bill a
    negative remainder, equal quantities bill zero. The quote must validate
    the SAME net amount, otherwise the confirmed total diverges from the
    actual invoice delta. Routing must also mirror the command's
    doctor-aware entry preference (ADR-001): an explicit specialist_id
    never merges into another doctor's same-tag queue. Read-only: reuses
    the service's own routing/payload predicates instead of duplicating
    them (no drift).

    Codex R8 #3115 (P1/P2):
    - per-item routing: явный queue_entry_id позиции выбирает запись, как и
      в команде (одинаковый service_id под разными врачами не мутирует
      «ближайшую» запись);
    - Codex R12 PR 3118 (P1): возвращает ВТОРОЕ значение — amount_override:
      ГОТОВУЮ знаковую сумму снижения (LIFO-слои: цена единицы каждого слоя
      × потреблённые единицы, _plan_lifo_consumption). При многослойном
      потреблении единой цены за единицу не существует, поэтому возвращается
      сумма, а не цена за единицу. Для роста — None (каталог × дельта);
    - Codex R12 PR 3118 (P2): гвард НЕ-редактируемого состояния
      (_assert_decrease_allowed) зеркалится в квоту ДО выпуска токена —
      снижение поверх оплаченного/processing счёта, инициализированного
      провайдерского pending-платежа или терминального визита отвечает 400
      вместо ложного подтверждения;
    - lock=True (save-ревалидация) фиксирует выбранную запись FOR UPDATE
      до конца транзакции — отмена записи между ревалидацией и применением
      не меняет маршрутизацию/дельту.
    """
    edit_service = RegistrarEditDeltaService(db)
    queue_tag = service.queue_tag or service.department_key
    if not queue_tag:
        # Codex R10 #3095 (P2): the command REJECTS an unroutable service
        # (apply → ValueError "Service {id} has no queue tag" → 400). The
        # quote mirrors that gate instead of billing the full quantity for
        # a service the save can never accept.
        raise HTTPException(
            status_code=400,
            detail=f"Service {service.id} has no queue tag",
        )
    item_preferred: set[int] = (
        {int(queue_entry_id)} if queue_entry_id is not None else preferred_entry_ids
    )
    try:
        entry = edit_service._find_active_entry(
            patient_id=patient_id,
            queue_tag=queue_tag,
            target_date=target_date,
            preferred_entry_ids=item_preferred,
            specialist_id=specialist_id,
            lock=lock,
            # Codex R11 #3115 (P1): явный queue_entry_id строг и в квоте —
            # устаревшая идентичность отклоняется ДО выпуска токена (иначе
            # токен подтверждал дельту, посчитанную по чужой записи).
            strict_entry_id=queue_entry_id,
        )
    except ValueError as exc:
        # Команда конвертирует ValueError в 400 на эндпоинте; квота
        # отвечает тем же 400 с тем же сообщением — контракт один.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payloads = (
        edit_service._find_service_payloads(
            edit_service._coerce_services(entry.services), service
        )
        if entry is not None
        else []
    )
    existing_qty = sum(int(edit_service._payload_quantity(p)) for p in payloads)
    if removal_service_ids is not None:
        try:
            edit_service._assert_partial_service_removal(
                entry=entry, service_ids=removal_service_ids, target_exists=existing_qty > 0,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if requested_qty > existing_qty:
        edit_service._assert_doctor_eligibility_for_addition(
            service=service,
            specialist_id=specialist_id,
            entry=entry,
            target_date=target_date,
        )

    if entry is None:
        # Codex R11 #3095 (P2): the command routes a no-entry edit to
        # _create_new_queue_entry → _resolve_daily_queue, which refuses
        # ("No active queue exists for queue_tag=...; specialist_id is
        # required") when neither the item nor the service supplies a
        # specialist. Mirror that gate HERE, read-only, BEFORE the token is
        # issued: a confirmed quote for a command the save can never accept
        # is a false confirmation (save-time token revalidation repeats the
        # successful quote, then the mutation returns 400). The resolution
        # expression is IDENTICAL to _resolve_daily_queue (item specialist
        # or the service's default doctor) — no drift.
        #
        # PR #3438 owner-verdict P1 (round 3): mirror the command's NEW
        # resource branch too — a resource-routed non-consultation service
        # resolves to the resource queue WITHOUT a specialist (the save
        # delegates to get_or_create_daily_queue's registry branch, which
        # finds-or-creates the day's resource queue), so a missing doctor
        # must not pre-reject the quote the catalog already offered.
        resolved_specialist_id = specialist_id or service.doctor_id
        resource_routed = not service.is_consultation and (
            service_routes_to_resource_queue(db, service, target_date)
        )
        if not resource_routed:
            target_queue_exists = (
                db.query(DailyQueue.id)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.queue_tag == queue_tag,
                    DailyQueue.active.is_(True),
                )
                .first()
                is not None
            )
            if not target_queue_exists and not resolved_specialist_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No active queue exists for queue_tag={queue_tag}; "
                        "specialist_id is required"
                    ),
                )
        return requested_qty, None
    delta = requested_qty - existing_qty
    if delta:
        edit_service.require_editable_visit_prices(entry)
    if not payloads:
        return requested_qty, None
    if delta < 0:
        # Codex R12 PR 3118 (P2): гвард НЕ-редактируемого состояния зеркалится
        # в квоту ДО выпуска токена. Оплаченный/processing счёт,
        # инициализированный провайдерский pending-платёж или терминальный
        # визит делают снижение невозможным: подтверждать его в квоте нельзя —
        # команда после успешной ревалидации отвергла бы команду (400),
        # состояние не изменилось бы, а регистратор получил ложное
        # подтверждение. ValueError команды конвертируется в 400 так же,
        # как гейт маршрутизации выше.
        try:
            edit_service._assert_decrease_allowed(entry=entry)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Codex R12 PR 3118 (P1): LIFO-зеркало снижения — точная сумма
        # потреблённых слоёв (цена единицы слоя × единицы), ровно то, что
        # спишет команда. При многослойном потреблении единой цены за единицу
        # нет — возвращаем ГОТОВУЮ сумму (amount_override), а не единичную
        # цену (см. вызов в _quote_core). Для старых строк без сохранённой
        # цены используем цену каталога, как в команде.
        consumption = edit_service._plan_lifo_consumption(
            entry=entry,
            payloads=payloads,
            units_to_remove=-delta,
            fallback_unit_price=Decimal(str(service.price or 0)),
        )
        decrease_amount = -sum(
            (charge * Decimal(units) for _, units, charge in consumption), Decimal("0")
        )
        return delta, decrease_amount
    return delta, None


def _quote_core(
    db: Session,
    quote_req: CartQuoteRequest,
    lock_pricing_rows: bool = False,
    registration_settings: dict[str, Any] | None = None,
    expected_entry_updated_at: dict[int, str] | None = None,
) -> CartQuoteResponse:
    """Shared pricing core for /registrar/cart/quote AND the save-time
    revalidation of the confirmed quote (Codex R3 #3095 P1). Raises the same
    HTTP errors either way; returns the quote with its binding token.

    Fix D: read-only предварительный расчёт цены корзины БЕЗ сохранения.

    Переиспользует те же настройки и тот же хелпер скидок, что и путь
    сохранения /registrar/cart (_load_registration_discount_settings +
    _apply_service_discount) — frontend больше не дублирует бизнес-правила
    скидок, и подтверждённая сумма совпадает с суммой invoice.

    Отсутствие цены у услуги — это НЕ 0: endpoint отвечает 409 с указанием
    услуги, чтобы регистратор увидел проблему до сохранения.
    """
    effective_discount_mode = _resolve_effective_discount_mode(quote_req)
    if quote_req.pricing_mode == "edit_delta":
        require_edit_delta_discount_mode(effective_discount_mode, all_free=quote_req.all_free)
    elif str(effective_discount_mode).strip().casefold() == "benefit":
        raise HTTPException(status_code=409, detail="Для льготы требуется подтверждение администратора")
    # Codex R13 #3095 (P2): canonicalize duplicate service rows for the
    # full-update pricing mode. Pricing in this mode depends ONLY on
    # (service_id, quantity) and catalog pricing. Two rows for the same
    # service with quantities 1 and 2 price like one row with quantity 3.
    # full_update_online_entry merges duplicate
    # rows before token revalidation and mutation; if the quote priced the
    # unmerged rows, the confirmed token could never match the merged save —
    # or, before that fix, the registrar confirmed three units while the
    # command created two one-unit entries. Quote and save now share ONE
    # canonical representation.
    if quote_req.pricing_mode == "full_update" and len(quote_req.items) > 1:
        _qty_by_service: dict[int, int] = {}
        _first_by_service: dict[int, CartQuoteItemRequest] = {}
        for item_req in quote_req.items:
            if item_req.service_id not in _qty_by_service:
                _qty_by_service[item_req.service_id] = item_req.quantity
                _first_by_service[item_req.service_id] = item_req
            else:
                _qty_by_service[item_req.service_id] += item_req.quantity
        if len(_qty_by_service) != len(quote_req.items):
            quote_req.items = [
                _first_by_service[sid].model_copy(update={"quantity": qty})
                for sid, qty in _qty_by_service.items()
            ]
    qr_all_free = quote_req.pricing_mode == "full_update" and effective_discount_mode == "all_free"
    # Codex R6 #3095 (P2): the save-time revalidation passes ITS OWN locked
    # settings snapshot in — quote and save are then priced from the exact
    # same values even for settings rows that do not exist yet (FOR UPDATE
    # cannot lock a row that is absent, so a concurrent admin INSERT of a
    # previously-missing key must not change the invoice after the token
    # was accepted).
    if registration_settings is None:
        registration_settings = _load_registration_discount_settings(db, lock_rows=lock_pricing_rows)

    # Ordinary edit-delta items are approved at the catalogue price.
    # QR All Free deliberately retains a pending decision and its baseline.
    if quote_req.pricing_mode == "edit_delta":
        approval_status = "approved"
    elif quote_req.pricing_mode == "full_update":
        approval_status = (
            "pending" if effective_discount_mode == "all_free" else "approved"
        )
    elif effective_discount_mode == "all_free":
        approval_status = (
            "pending"
            if not registration_settings["all_free_auto_approve"]
            else "approved"
        )
    else:
        approval_status = "approved"

    total_amount = Decimal("0")
    quote_currency: str | None = None
    items: list[CartQuoteItemResponse] = []
    if qr_all_free and not quote_req.items:
        raise HTTPException(status_code=409, detail="Визит не содержит услуг")

    # Codex R9 #3095 (P2): the save path acquires ALL service row locks in ONE
    # deterministic (sorted id) order BEFORE calculating items. When only the
    # default pricing settings exist, the settings query locks no rows, so two
    # concurrent token-bound saves could reach the per-item loop together and
    # lock the same services in opposite orders — a classic lock-order
    # deadlock; PostgreSQL aborts one save. Sorted bulk acquisition gives every
    # transaction the same global order, so waits always form a chain, never a
    # cycle. Behavior (prices, 404s, token) is unchanged — this only fixes HOW
    # the locks are taken.
    service_row_map: dict[int, Service] = {}
    if lock_pricing_rows:
        _lock_ids = sorted({int(item_req.service_id) for item_req in quote_req.items})
        if _lock_ids:
            # One FOR UPDATE scan in sorted id order = deterministic lock
            # acquisition; the returned rows fill the identity map reused by
            # the item loop (no second read, same transaction snapshot).
            for _svc in (
                db.query(Service)
                .filter(Service.id.in_(_lock_ids))
                .order_by(Service.id)
                .with_for_update()
                .populate_existing()
                .all()
            ):
                service_row_map[int(_svc.id)] = _svc

    # Edit saves already hold the patient/Visit locks. Complete their queue
    # snapshot only after catalog locks, before version checks or routing.
    edit_context = db.info.get("registrar_edit_lock_context")
    if (lock_pricing_rows and quote_req.pricing_mode == "edit_delta" and
            edit_context is not None and edit_context.transaction is db.get_transaction() and
            edit_context.nested_transaction is db.get_nested_transaction()):
        if edit_context.patient_id != quote_req.patient_id:
            raise HTTPException(status_code=409, detail="Контекст пациента изменился")
        RegistrarEditDeltaService(db).lock_queue_context(
            [item_req.service_id for item_req in quote_req.items], catalog_prelocked=True
        )

    # Lock the complete version set after catalog locks, before quote routing
    # locks individual entries. Otherwise two edits to different entries can
    # each hold one row and then wait for the other's version-check lock.
    if lock_pricing_rows and expected_entry_updated_at:
        try:
            RegistrarEditDeltaService(db)._assert_entries_not_concurrently_modified(
                expected_entry_updated_at, patient_id=quote_req.patient_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # W2-PR2: канонический день edit-квоты — зеркало RegistrarEditDelta
    # Service.apply (та же resolve_edit_target_day): день предпочтённых записей,
    # а не запрошенная строка. Прежний контракт «фронт шлёт getLocalISODate()»
    # квотировал и сохранял правку записи на будущую дату в «сегодня».
    # Резолв один на запрос (не на позицию); мультидневный набор preferred —
    # громкий 400, как в команде. Revalidation проходит через ТУ ЖЕ ветку с
    # теми же сырыми входами → токен квоты остаётся согласованным.
    edit_target_date = quote_req.target_date
    if (
        quote_req.pricing_mode == "edit_delta"
        and quote_req.patient_id is not None
        and quote_req.preferred_entry_ids
    ):
        try:
            edit_target_date = RegistrarEditDeltaService(db).resolve_edit_target_day(
                patient_id=quote_req.patient_id,
                preferred_entry_ids=set(quote_req.preferred_entry_ids),
                requested_target_date=quote_req.target_date or date.today(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    # Codex R7 #3095 (P2): зеркалируем ПОСЛЕДОВАТЕЛЬНОЕ состояние команды.
    # RegistrarEditDeltaService.apply обрабатывает строки по очереди: вторая
    # дублирующая строка того же (service_id, specialist_id) видит позицию,
    # созданную/пополненную первой. Квота накапливает уже подтверждённые
    # дельты внутри одного прохода — иначе токен покрывает больше единиц,
    # чем выставит команда.
    removal_targets: dict[int, set[int]] = {}
    if any(item.quantity == 0 for item in quote_req.items):
        if (
            quote_req.pricing_mode != "edit_delta"
            or quote_req.patient_id is None
            or edit_target_date is None
        ):
            raise HTTPException(status_code=400, detail="Нулевое количество допустимо только при удалении услуги из записи")
        try:
            removal_targets = partial_removal_targets([
                (item.service_id, item.quantity, item.queue_entry_id) for item in quote_req.items
            ])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    _edit_delta_covered: dict[tuple[int, int | None], int] = {}

    for item_req in quote_req.items:
        if int(item_req.service_id) in service_row_map:
            service: Service | None = service_row_map[int(item_req.service_id)]
        else:
            # Codex R4 #3095 (P1): the save path holds the row locks to the end
            # of its transaction, so a concurrent price change cannot slip in
            # between token revalidation and invoice calculation. (Quote paths
            # without lock_pricing_rows read without FOR UPDATE.)
            service = db.query(Service).filter(Service.id == item_req.service_id).first()
        if not service:
            raise HTTPException(
                status_code=404,
                detail=f"Услуга с ID {item_req.service_id} не найдена",
            )

        if quote_req.pricing_mode == "cart" or qr_all_free:
            currency = service.currency
            if service.price is None:
                raise HTTPException(status_code=409, detail=f"Для услуги «{service.name}» не указана цена")
            if (not service.active or not Decimal(str(service.price)).is_finite()
                    or Decimal(str(service.price)) < 0 or not isinstance(currency, str)
                    or len(currency) != 3 or not currency.isascii() or not currency.isalpha()
                    or currency != currency.upper()):
                raise HTTPException(status_code=409, detail="Цена или валюта услуги недоступна")
            if quote_currency is not None and quote_currency != currency:
                raise HTTPException(status_code=409, detail="Услуги с разными валютами нельзя объединить в один счёт")
            quote_currency = currency
            if item_req.quantity > 2147483647:
                raise HTTPException(status_code=422, detail="Количество услуги превышает допустимое значение")
            if (
                quote_req.pricing_mode == "cart" and item_req.custom_price is not None
                and item_req.custom_price != service.price
            ):
                raise HTTPException(status_code=409, detail="Изменение цены требует согласования")
        elif service.price is None:
            raise HTTPException(
                status_code=409,
                detail=f"Для услуги «{service.name}» не указана цена",
            )

        # Edit-delta uses the same catalogue prices and stored layers as
        # the invoice mutation in RegistrarEditDeltaService.
        # Codex R12 PR 3118 (P1): amount_override снижения (готовая знаковая
        # сумма LIFO-слоёв) — только в edit_delta; остальные режимы не имеют
        # слоёв и считаются unit × qty.
        decrease_amount: Decimal | None = None
        if quote_req.pricing_mode == "edit_delta":
            base_price = Decimal(str(service.price))
            unit_final = base_price
            discount_percent = 0
            # Codex R10 #3095 (P2): the command's routing gate mirrors into
            # the quote for BOTH context paths — without the edit context the
            # helper below is not called at all, so an unroutable service
            # must be rejected here (same reason as the save: 400 "no queue
            # tag"), never confirmed as a billable full quantity.
            if not (service.queue_tag or service.department_key):
                raise HTTPException(
                    status_code=400,
                    detail=f"Service {service.id} has no queue tag",
                )
            # Codex R6 #3095 (P2): with edit context the billable quantity is
            # the DELTA the command will actually bill. W2-PR1: the delta is
            # SIGNED (requested − existing): increases bill the remainder,
            # decreases bill negative, equal quantities bill zero — the quote
            # mirrors the command's target-state semantics exactly.
            # Codex R8 #3115 (P1/P2): per-item queue_entry_id routing mirror +
            # decrease quotes price the RECORDED unit charge (full-update rows
            # store line totals), the same value the command subtracts.
            # W2-PR2: день — канонический день редактируемых записей.
            # Codex R12 PR 3118 (P1): снижение возвращает amount_override —
            # ГОТОВУЮ сумму потреблённых LIFO-слоёв (единая цена за единицу
            # при многослойном потреблении отсутствует); рост остаётся
            # каталог × дельта (при слоях это ТОЧНО сумма команды).
            # Codex R7/R15 #3095 (P2): ПОСЛЕДОВАТЕЛЬНОЕ зеркало команды:
            # delta_i = target_i − existing − Σ delta_j (j<i) — эквивалентно
            # строке с последовательно-эффективным requested (target −
            # Σ delta_j): LIFO-потребление снижения и его amount_override
            # считаются для скорректированной дельты. Дельта ЗНАКОВАЯ —
            # covered копит её без клампа (дубликат-снижение валидно и
            # гвардится как обычное снижение).
            # Codex R15 #3118 (P1): ключ покрытия — (service_id,
            # queue_entry_id): команда маршрутизирует по (patient, day,
            # queue_tag), количество внутри записи суммируется по сервису
            # независимо от специалиста (_find_service_payload), а явные
            # queue_entry_id — независимые позиции (строгий селектор R11).
            _covered_key = (
                int(item_req.service_id),
                item_req.queue_entry_id,
            )
            _sequential_requested = item_req.quantity - _edit_delta_covered.get(
                _covered_key, 0
            )
            if quote_req.patient_id is not None and edit_target_date is not None:
                billable_qty, decrease_amount = _edit_delta_quote_context(
                    db,
                    service=service,
                    requested_qty=_sequential_requested,
                    patient_id=quote_req.patient_id,
                    # W2-PR2: канонический день (день редактируемых записей).
                    target_date=edit_target_date,
                    preferred_entry_ids=set(quote_req.preferred_entry_ids),
                    specialist_id=item_req.specialist_id,
                    queue_entry_id=item_req.queue_entry_id,
                    lock=lock_pricing_rows,
                    all_free=effective_discount_mode == "all_free",
                    removal_service_ids=(
                        removal_targets[item_req.queue_entry_id] if item_req.quantity == 0 else None
                    ),
                )
            else:
                billable_qty = _sequential_requested
            _edit_delta_covered[_covered_key] = (
                _edit_delta_covered.get(_covered_key, 0) + billable_qty
            )
        elif quote_req.pricing_mode == "full_update":
            # QR All Free retains the ordinary price until an admin approves it.
            base_price = Decimal(str(service.price))
            if service.is_consultation and effective_discount_mode in ("repeat", "benefit"):
                unit_final = Decimal("0")
                discount_percent = 100
            else:
                unit_final = base_price
                discount_percent = 0
        else:
            # Mode 'cart' — зеркало пути сохранения /registrar/cart:
            # врачебная переопределённая цена (Codex R1 #3095 P2), затем
            # скидочный хелпер SSOT.
            base_price = (
                item_req.custom_price
                if item_req.custom_price is not None
                else Decimal(str(service.price))
            )
            unit_final = _apply_service_discount(
                base_price,
                effective_discount_mode,
                registration_settings,
                service.is_consultation,
            )
            # Процент скидки для отображения (зеркало _apply_service_discount)
            if effective_discount_mode == "all_free":
                discount_percent = 100
            elif effective_discount_mode == "repeat" and service.is_consultation:
                raw = Decimal(
                    str(registration_settings.get("repeat_visit_discount", 0) or 0)
                )
                discount_percent = int(max(Decimal("0"), min(raw, Decimal("100"))))
            elif effective_discount_mode == "benefit" and service.is_consultation:
                discount_percent = (
                    100 if registration_settings.get("benefit_consultation_free", True) else 0
                )
            else:
                discount_percent = 0

        # Codex R6 #3095 (P2): edit_delta prices the BILLABLE delta quantity;
        # the other modes price the full requested quantity.
        priced_qty = billable_qty if quote_req.pricing_mode == "edit_delta" else item_req.quantity

        with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
            if decrease_amount is not None:
                final_price = decrease_amount.quantize(Decimal("0.01"))
            else:
                final_price = (unit_final * Decimal(priced_qty)).quantize(Decimal("0.01"))
            if quote_req.pricing_mode == "full_update" and not qr_all_free:
                final_price = Decimal(int(unit_final * Decimal(item_req.quantity)))
            total_amount += final_price
        # The queue projection still has a signed integer amount column.
        if qr_all_free and total_amount >= Decimal("2147483648"):
            raise HTTPException(status_code=422, detail="Стоимость оформления превышает допустимое значение")
        if quote_req.pricing_mode == "cart" and total_amount > Decimal("9999999999.99"):
            raise HTTPException(status_code=422, detail="Стоимость оформления превышает допустимое значение")

        items.append(
            CartQuoteItemResponse(
                service_id=service.id,
                service_name=service.name,
                unit_price=base_price,
                quantity=priced_qty,
                discount_percent=discount_percent,
                final_price=final_price,
            )
        )

    return CartQuoteResponse(
        items=items,
        total_amount=total_amount,
        currency=quote_currency,
        approval_status=approval_status,
        quote_token=_quote_token(items, total_amount, approval_status, quote_req, quote_currency),
    )


_CART_CONFLICT_RESPONSE = {
    "description": "Условия расчёта требуют проверки или согласования",
    "content": {"application/json": {"schema": {
        "type": "object", "properties": {"detail": {"type": "string"}}, "required": ["detail"],
    }}},
}


@router.post("/registrar/cart/quote", response_model=CartQuoteResponse, responses={409: _CART_CONFLICT_RESPONSE})
def quote_cart_prices(
    quote_req: CartQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Fix D: read-only предварительный расчёт цены корзины (endpoint)."""
    _ = current_user
    return _quote_core(db, quote_req)


def _assert_quote_token_matches(
    db: Session,
    *,
    items: list[CartQuoteItemRequest],
    discount_mode: str,
    all_free: bool,
    pricing_mode: str,
    quote_token: str | None,
    patient_id: int | None = None,
    target_date: date | None = None,
    preferred_entry_ids: list[int] | None = None,
    expected_entry_updated_at: dict[int, str] | None = None,
    locked_settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Save-command revalidation shared by /registrar/cart, edit-delta and
    full-update (Codex R4 #3095 P1). Recomputes the quote on the CURRENT
    catalog/settings with row locks held to the end of the caller's
    transaction and rejects a stale token with 409.

    Codex R6 #3095 (P2): the edit-delta command MUST revalidate with the
    SAME edit context (patient_id/target_date/preferred entries) the quote
    used — the billable quantity is a routing-dependent delta, so a
    context-less recompute would price the full quantity and falsely reject
    the confirmed token with 409.

    Codex R6 #3095 (P2): returns the LOCKED settings snapshot the fresh
    quote was priced from. The caller prices the save from THIS snapshot
    instead of re-reading settings ("price the save directly from the
    validated values"): FOR UPDATE cannot lock settings rows that do not
    exist yet, so a concurrent admin INSERT (admin settings endpoint) of a
    previously-missing key between revalidation and the save's own reload
    could otherwise flip the invoice to the newly inserted discount while
    the token still validated the old one. With the snapshot the invoice is
    computed from exactly the values the registrar confirmed. Returns None
    when no token was supplied unless the writer needs locked catalog
    prices to persist approval evidence for a legacy caller.
    """
    qr_all_free = pricing_mode == "full_update" and (all_free or discount_mode == "all_free")
    if not quote_token and not qr_all_free:
        return None
    settings_snapshot = locked_settings
    if settings_snapshot is None:
        # QR All Free always requires an administrator decision and uses the catalog.
        settings_snapshot = {} if qr_all_free else _load_registration_discount_settings(db, lock_rows=True)
    fresh_quote = _quote_core(
        db,
        CartQuoteRequest(
            items=items,
            discount_mode=discount_mode,
            all_free=all_free,
            pricing_mode=pricing_mode,
            patient_id=patient_id,
            target_date=target_date,
            preferred_entry_ids=list(preferred_entry_ids or []),
        ),
        lock_pricing_rows=True,
        registration_settings=settings_snapshot,
        expected_entry_updated_at=expected_entry_updated_at,
    )
    if quote_token and fresh_quote.quote_token != quote_token:
        logger.warning(
            "REGISTRATION: stale quote token — pricing changed since confirmation; "
            "current total: %s",
            fresh_quote.total_amount,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Цены или скидки изменились после подтверждения — подтвердите новую сумму. "
                f"Текущая сумма корзины: {fresh_quote.total_amount} {fresh_quote.currency or ''}".rstrip()
            ),
        )
    return settings_snapshot


@router.post("/registrar/cart/edit-delta", response_model=EditDeltaResponse, responses={409: _CART_CONFLICT_RESPONSE})
def apply_registrar_cart_edit_delta(
    request: EditDeltaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    require_edit_delta_discount_mode(request.discount_mode, all_free=request.all_free)
    try:
        # Codex R4 #3095 (P1): bind the confirmed edit quote to the command —
        # revalidate BEFORE any mutation (the edit-delta pricing rules are
        # mirrored by the quote's edit_delta mode; custom_price is not part of
        # the edit-delta contract).
        edit_service = RegistrarEditDeltaService(db)
        edit_service.lock_edit_context(request.patient_id, current_user, lock_queues=False)
        _assert_quote_token_matches(
            db,
            items=[
                # Codex R13 #3095 (P2): mirror the specialist the QUOTE was
                # computed with. The billable quantity is routing-dependent: for
                # a service with no default doctor and no active same-day queue
                # the quote succeeds with the browser-selected specialist, while
                # a specialist-less revalidation hits the R11 gate
                # ("specialist_id is required" 400) BEFORE the mutation can use
                # request.services[*].specialist_id — the save rejected the very
                # command the registrar had just confirmed.
                CartQuoteItemRequest(
                    service_id=s.service_id,
                    quantity=s.quantity,
                    specialist_id=s.specialist_id,
                    # Codex R8 #3115 (P1): зеркало per-item маршрутизации
                    queue_entry_id=s.queue_entry_id,
                )
                for s in request.services
            ],
            discount_mode=request.discount_mode,
            all_free=request.all_free,
            pricing_mode="edit_delta",
            quote_token=request.quote_token,
            # Codex R6 #3095 (P2): revalidate under the SAME edit context the
            # quote was computed with — the billable quantity is a
            # routing-dependent delta.
            patient_id=request.patient_id,
            target_date=request.target_date,
            preferred_entry_ids=request.existing_queue_entry_ids,
            expected_entry_updated_at=request.expected_entry_updated_at,
        )
        result = edit_service.apply(
            patient_id=request.patient_id,
            services=[
                RegistrarEditDeltaItem(
                    service_id=item.service_id,
                    quantity=item.quantity,
                    specialist_id=item.specialist_id,
                    # Codex R8 #3115 (P1): правка мутирует именованную запись
                    queue_entry_id=item.queue_entry_id,
                )
                for item in request.services
            ],
            target_date=request.target_date,
            payment_method=request.payment_method,
            discount_mode=request.discount_mode,
            all_free=request.all_free,
            patient_data=(
                request.patient_data.model_dump(exclude_none=True)
                if request.patient_data
                else None
            ),
            existing_queue_entry_ids=request.existing_queue_entry_ids,
            expected_entry_updated_at=request.expected_entry_updated_at,
            current_user=current_user,
        )
        return EditDeltaResponse(**result)
    except DBAPIError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if sqlstate == "40P01":
            raise HTTPException(
                status_code=409,
                detail="Параллельное изменение записи. Повторите операцию.",
            ) from exc
        logger.exception("REGISTRATION: edit delta database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления записи",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        logger.exception(
            "REGISTRATION: edit delta failed",
            extra={"error_class": exc.__class__.__name__},
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления записи",
        )


class PriceOverrideApprovalRequest(BaseModel):
    override_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: str | None = None


class PriceOverrideListResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    service_name: str
    doctor_name: str
    doctor_specialty: str
    patient_name: str | None
    original_price: Decimal
    new_price: Decimal
    # DERMAPRICE-BE-002 end-to-end (audit #3892, group 16 follow-up): the
    # registrar reviewer also sees the visit's ACTUAL before-price captured
    # at request time and the delta relative to it — the catalogue
    # original_price keeps its immutable reference semantics.
    visit_price_before: Decimal | None = None
    visit_price_difference: Decimal | None = None
    reason: str
    details: str | None
    status: str
    available_actions: list[str]
    can_approve: bool
    can_reject: bool
    created_at: datetime


def _price_override_available_actions(override_status: str) -> list[str]:
    if override_status == "pending":
        return ["approve", "reject"]
    return []


@router.get(
    "/registrar/price-overrides", summary="Получить все изменения цен для одобрения",
    response_model=list[PriceOverrideListResponse],
)
def get_pending_price_overrides(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(financial_reviewer),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PriceOverrideListResponse]:
    """
    Получить список изменений цен для одобрения регистратурой

    REGPRICE-BE-004 (audit #3892, group 16): the queue is paginated over a
    deterministic ``(created_at DESC, id DESC)`` order and the FULL filtered
    total is exposed via the ``X-Total-Count`` header — a bare 100-row
    newest-first window silently hid older pending requests with no way to
    reach them from the registrar UI.
    """
    try:
        # Explicit join conditions on the OVERRIDE's foreign keys. The
        # previous implicit ``.join(Service).join(Doctor)`` chain inferred
        # ``Service.doctor_id == Doctor.id`` for the second hop — catalogue
        # services (doctor_id NULL) then silently disappeared from the
        # registrar queue, an even harsher drop than REGPRICE-BE-004
        # described.
        query = (
            db.query(DoctorPriceOverride)
            .join(Service, DoctorPriceOverride.service_id == Service.id)
            .outerjoin(Doctor, DoctorPriceOverride.doctor_id == Doctor.id)
        )

        if status_filter != "all":
            query = query.filter(DoctorPriceOverride.status == status_filter)

        total = query.count()
        response.headers["X-Total-Count"] = str(total)

        overrides = (
            query.order_by(
                DoctorPriceOverride.created_at.desc(), DoctorPriceOverride.id.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for override in overrides:
            available_actions = _price_override_available_actions(override.status)
            # Получаем данные визита и пациента
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            patient_name = None
            if visit:
                # Здесь нужно получить имя пациента из модели Patient
                # Пока используем заглушку
                patient_name = f"Пациент #{visit.patient_id}"

            result.append(
                PriceOverrideListResponse(
                    id=override.id,
                    visit_id=override.visit_id,
                    service_id=override.service_id,
                    service_name=override.service.name,
                    doctor_name=f"Врач #{override.doctor.id}" if override.doctor else "Не назначен",
                    doctor_specialty=(override.doctor.specialty or "") if override.doctor else "",
                    patient_name=patient_name,
                    original_price=override.original_price,
                    new_price=override.new_price,
                    visit_price_before=override.visit_price_before,
                    visit_price_difference=(
                        override.new_price - override.visit_price_before
                        if override.visit_price_before is not None
                        else None
                    ),
                    reason=override.reason,
                    details=override.details,
                    status=override.status,
                    available_actions=available_actions,
                    can_approve="approve" in available_actions,
                    can_reject="reject" in available_actions,
                    created_at=override.created_at,
                )
            )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/registrar/price-override/approve", summary="Одобрить или отклонить изменение цены",
    response_model=dict[str, Any],
)
def approve_price_override(
    approval_data: PriceOverrideApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(financial_reviewer),
) -> dict[str, Any]:
    """Рассмотреть изменение цены и обновить черновой счёт при одобрении."""
    try:
        try:
            bearer = capture_profile_bearer(request, current_user)
        except ProfileBearerInvalid:
            raise HTTPException(status_code=401, detail="Сессия недействительна") from None
        override = PriceOverrideApprovalService(db).process(
            override_id=approval_data.override_id,
            action=approval_data.action,
            rejection_reason=approval_data.rejection_reason,
            approver_id=current_user.id,
            bearer=bearer,
        )
    except PriceOverrideApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    message = (
        "Изменение цены одобрено"
        if override.status == "approved"
        else "Изменение цены отклонено"
    )
    return {
        "success": True,
        "message": message,
        "override_id": override.id,
        "new_status": override.status,
    }


# ===================== УПРАВЛЕНИЕ ЛЬГОТАМИ ALL FREE =====================


class AllFreeApprovalRequest(BaseModel):
    visit_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: str | None = None


class AllFreeVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str | None
    patient_phone: str | None
    services: list[str]
    total_original_amount: Decimal
    doctor_name: str | None
    doctor_specialty: str | None
    visit_date: date | None
    visit_time: str | None
    notes: str | None
    created_at: datetime
    approval_status: str
    available_actions: list[str]
    can_approve: bool
    can_reject: bool


def _all_free_available_actions(approval_status: str, *, can_review_invitation: bool = False) -> list[str]:
    if approval_status == "pending":
        return ["approve", "reject"]
    if can_review_invitation and approval_status in {"approved", "rejected"}:
        return ["review_invitation"]
    return []


@router.get(
    "/admin/all-free-requests", summary="Получить заявки All Free для одобрения",
    response_model=list[AllFreeVisitResponse],
)
def get_all_free_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(financial_admin),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AllFreeVisitResponse]:
    """
    Получить список заявок All Free для одобрения администратором
    """
    try:
        baseline_amount = (
            db.query(AllFreeRequest.baseline_total)
            .filter(
                AllFreeRequest.visit_id == Visit.id,
                AllFreeRequest.visit_id_snapshot == Visit.id,
                AllFreeRequest.patient_id == Visit.patient_id,
                AllFreeRequest.patient_id_snapshot == Visit.patient_id,
                AllFreeRequest.encounter_id == Visit.encounter_id,
                AllFreeRequest.encounter_id_snapshot == Visit.encounter_id,
                AllFreeRequest.status == Visit.approval_status,
            )
            .order_by(AllFreeRequest.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = db.query(Visit, baseline_amount).filter(Visit.discount_mode == "all_free")

        if status_filter != "all":
            query = query.filter(Visit.approval_status == status_filter)

        visits = query.order_by(Visit.created_at.desc()).limit(limit).all()

        # The review command reloads and verifies the signed, locked context.
        invitation_reviewer = current_user.is_superuser or normalize_role_value(current_user.role) == "admin"
        result = []
        for visit, saved_amount in visits:
            available_actions = _all_free_available_actions(
                visit.approval_status,
                can_review_invitation=bool(
                    invitation_reviewer and visit.status == "pending_confirmation"
                    and visit.confirmation_token is None and saved_amount is not None
                ),
            )
            # Получаем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            total_original_amount = saved_amount if saved_amount is not None else Decimal('0')

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    service_names.append(service.name)
                    if saved_amount is None:
                        total_original_amount += (service.price or Decimal('0')) * vs.qty

            # Получаем данные врача
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                try:
                    doctor = (
                        db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    )
                    if doctor:
                        # Получаем имя врача из связанного пользователя
                        # [OK] ИСПРАВЛЕНО: Используем явный запрос вместо relationship, чтобы избежать ошибок
                        if doctor.user_id:
                            user = (
                                db.query(User).filter(User.id == doctor.user_id).first()
                            )
                            if user:
                                # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                                doctor_name = (
                                    (user.full_name or user.username)
                                    if user
                                    else f"Врач #{doctor.id}"
                                )
                            else:
                                doctor_name = f"Врач #{doctor.id}"
                        else:
                            doctor_name = f"Врач #{doctor.id}"
                        doctor_specialty = doctor.specialty
                except Exception as e:
                    logger.warning(
                        "get_all_free_requests: Ошибка получения данных врача для visit %d: %s",
                        visit.id,
                        e,
                        exc_info=True,
                    )
                    doctor_name = f"Врач #{visit.doctor_id}"
                    doctor_specialty = None

            # [OK] ИСПРАВЛЕНО: Получаем реальные данные пациента
            patient_name = f"Пациент #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    # Формируем ФИО пациента
                    name_parts = []
                    if patient.last_name:
                        name_parts.append(patient.last_name)
                    if patient.first_name:
                        name_parts.append(patient.first_name)
                    if patient.middle_name:
                        name_parts.append(patient.middle_name)
                    patient_name = (
                        ' '.join(name_parts)
                        if name_parts
                        else f"Пациент #{visit.patient_id}"
                    )
                    patient_phone = patient.phone

            result.append(
                AllFreeVisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    services=service_names,
                    total_original_amount=total_original_amount,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    notes=visit.notes,
                    created_at=visit.created_at,
                    approval_status=visit.approval_status,
                    available_actions=available_actions,
                    can_approve="approve" in available_actions,
                    can_reject="reject" in available_actions,
                )
            )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/admin/all-free-approve", summary="Одобрить или отклонить заявку All Free",
    response_model=dict[str, Any],
)
def approve_all_free_request(
    approval_data: AllFreeApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(financial_admin),
    http_request: Request = None,
) -> dict[str, Any]:
    """
    Одобрить или отклонить заявку All Free администратором
    """
    try:
        # Получаем визит
        visit = db.query(Visit).filter(Visit.id == approval_data.visit_id).first()

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        if visit.discount_mode != "all_free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Это не заявка All Free"
            )

        if visit.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заявка уже обработана (статус: {visit.approval_status})",
            )

        if http_request is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        bearer = capture_profile_bearer(http_request, current_user)
        request_id = (
            db.query(AllFreeRequest.id)
            .filter(
                AllFreeRequest.visit_id == visit.id,
                AllFreeRequest.status == "pending",
            )
            .scalar()
        )
        if request_id is None:
            raise HTTPException(status_code=409, detail="Обычные цены заявки требуют сверки")
        decision = AllFreeRequestService(db)._apply_unpublished_decision(
            request_id=request_id, action=approval_data.action, bearer=bearer,
        )
        if decision.status == "approved":
            message = "Заявка All Free одобрена"
        else:
            message = "Заявка All Free отклонена"
            if approval_data.rejection_reason:
                visit.notes = (visit.notes or "") + f"\nОтклонено: {approval_data.rejection_reason}"
        check_bearer_expiry(bearer)
        db.commit()
        db.refresh(visit)

        try:
            asyncio.run(
                notification_sender_service.send_all_free_decision_notification(
                    db=db,
                    visit=visit,
                    request_id=decision.request_id,
                    actor_user=current_user,
                    rejection_reason=approval_data.rejection_reason,
                )
            )
        except Exception as notification_error:
            logger.warning(
                "[FIX:NOTIFICATIONS] failed to publish all_free decision notification",
                extra={
                    "visit_id": visit.id,
                    "approval_status": visit.approval_status,
                    "actor_id": current_user.id,
                    "error": str(notification_error),
                },
            )

        return {
            "success": True,
            "message": message,
            "visit_id": visit.id,
            "new_status": decision.status,
        }

    except HTTPException:
        db.rollback()
        raise
    except AllFreeRequestError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    except FinancialFenceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сессия недоступна") from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== НАСТРОЙКИ ЛЬГОТ =====================


class BenefitSettingsRequest(BaseModel):
    repeat_visit_days: int = Field(
        default=21, ge=1, le=365
    )  # Окно повторного визита в днях
    repeat_visit_discount: int = Field(
        default=0, ge=0, le=100
    )  # Скидка на повторный визит в %
    benefit_consultation_free: bool = Field(
        default=True
    )  # Льготные консультации бесплатны
    all_free_auto_approve: bool = Field(default=False)  # Автоодобрение All Free заявок


class BenefitSettingsResponse(BaseModel):
    repeat_visit_days: int
    repeat_visit_discount: int
    benefit_consultation_free: bool
    all_free_auto_approve: bool
    updated_at: datetime
