from __future__ import annotations

import hashlib
import json
from typing import Any

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _apply_service_discount,
    _check_repeat_visit_eligibility,
    _load_registration_discount_settings,
    _resolve_effective_discount_mode,
)  # noqa: F401
from app.models.online_queue import DailyQueue


@router.post("/registrar/cart", response_model=CartResponse)
def create_cart_appointments(
    cart_data: CartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Создание корзины визитов с единым платежом
    Поддерживает: повторные/льготные визиты, All Free, динамические цены, очереди по queue_tag
    """
    effective_discount_mode = _resolve_effective_discount_mode(cart_data)

    # Codex R3 #3095 (P1): revalidate the CONFIRMED quote before any write.
    # An administrator may change a service price or a discount setting after
    # the registrar confirmed the preview; without this check /registrar/cart
    # silently created an invoice for a DIFFERENT amount. The token binds the
    # save command to the exact pricing the registrar confirmed; a mismatch
    # is a hard 409 — the registrar must re-confirm, not be over/undercharged.
    validated_settings: dict[str, Any] | None = None
    if cart_data.quote_token:
        flat_items = [
            CartQuoteItemRequest(
                service_id=s.service_id,
                quantity=s.quantity,
                custom_price=s.custom_price,
            )
            for visit_req in cart_data.visits
            for s in visit_req.services
        ]
        # Codex R6 #3095 (P2): price the save from the validated values —
        # the snapshot returned here is the LOCKED settings state the
        # confirmed quote was computed from; a concurrent admin INSERT of a
        # previously-missing settings row cannot flip the invoice after the
        # token passed.
        validated_settings = _assert_quote_token_matches(
            db,
            items=flat_items,
            discount_mode=cart_data.discount_mode,
            all_free=cart_data.all_free,
            pricing_mode="cart",
            quote_token=cart_data.quote_token,
        )

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
        # Валидация пациента
        # (Предполагаем, что пациент уже существует, так как он выбран в мастере)

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
        # Codex R6 #3095 (P2): when a quote token was validated, the settings
        # snapshot it produced IS the pricing truth for this save — do not
        # re-read (an unlocked reload would see settings rows inserted by the
        # admin endpoint after revalidation, which FOR UPDATE cannot lock).
        registration_settings = validated_settings or _load_registration_discount_settings(db)

        created_visits = []
        created_visit_amounts: dict[int, Decimal] = {}
        total_invoice_amount = Decimal('0')

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
            # Проверяем право на повторный визит
            if effective_discount_mode == "repeat" and visit_req.doctor_id:
                service_ids = [s.service_id for s in visit_req.services]
                repeat_visit_days = int(registration_settings["repeat_visit_days"])
                if not _check_repeat_visit_eligibility(
                    db,
                    cart_data.patient_id,
                    visit_req.doctor_id,
                    service_ids,
                    days_window=repeat_visit_days,
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Повторный визит недоступен: нет консультации у этого врача за последние {repeat_visit_days} дней",
                    )

            # [OK] ИСПРАВЛЕНО: Регистратор всегда создаёт подтверждённые записи
            # Фича-флаг "confirmation_before_queue" применяется только для онлайн-записей (телеграм/PWA)
            # Записи от регистратора сразу попадают в очередь
            visit_status = "confirmed"
            confirmed_at = datetime.now(UTC)
            confirmed_by = f"registrar_{current_user.id}"

            # [OK] ИСПРАВЛЕНО: Добавляем микрозадержку для разных created_at
            # Это гарантирует, что визиты одного пациента будут иметь разные временные метки
            if idx > 0:
                sleep(0.001)  # 1 миллисекунда задержки между визитами

            # Подготавливаем услуги для передачи в create_visit
            services_data = []
            visit_amount = Decimal("0")
            for service_item in visit_req.services:
                service = (
                    db.query(Service)
                    .filter(Service.id == service_item.service_id)
                    .first()
                )
                if not service:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Услуга с ID {service_item.service_id} не найдена",
                    )

                base_price = (
                    service_item.custom_price
                    if service_item.custom_price is not None
                    else service.price or Decimal("0")
                )
                item_price = _apply_service_discount(
                    Decimal(str(base_price)),
                    effective_discount_mode,
                    registration_settings,
                    service.is_consultation,
                )
                visit_amount += item_price * Decimal(service_item.quantity)

                services_data.append(
                    {
                        "service_id": service.id,
                        # ⭐ SSOT: используем canonical service_code helper
                        "code": service.service_code or get_service_code(service.id, db),
                        "name": service.name,
                        "qty": service_item.quantity,
                        "price": float(item_price),
                    }
                )

            # Создаём визит используя единую функцию create_visit для обеспечения Single Source of Truth
            from app.crud.visit import create_visit

            visit = create_visit(
                db=db,
                patient_id=cart_data.patient_id,
                doctor_id=visit_req.doctor_id,
                visit_date=visit_req.visit_date,
                visit_time=visit_req.visit_time,
                department=visit_req.department,
                notes=visit_req.notes,
                discount_mode=effective_discount_mode,
                services=services_data,
                status=visit_status,
                approval_status=(
                    "approved"
                    if effective_discount_mode != "all_free"
                    or registration_settings["all_free_auto_approve"]
                    else "pending"
                ),
                confirmed_at=confirmed_at,
                confirmed_by=confirmed_by,
                auto_status=False,  # Статус уже установлен выше
                notify=False,  # Уведомления отправляются отдельно
                log=True,
            )
            logger.info("REGISTRATION: Визит %d создан через create_visit()", visit.id)

            created_visits.append(visit)
            created_visit_amounts[visit.id] = visit_amount
            total_invoice_amount += visit_amount
            logger.info(
                "REGISTRATION: Визит %d создан успешно для пациента %d",
                visit.id,
                cart_data.patient_id,
            )

        # Создаём единый invoice
        logger.info("REGISTRATION: Создаём инвойс на сумму %s", total_invoice_amount)
        invoice = PaymentInvoice(
            patient_id=cart_data.patient_id,
            total_amount=total_invoice_amount,
            currency="UZS",
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

        # Assign queue entries for confirmed same-day visits via extracted seam.
        queue_numbers = {}
        today = date.today()

        queue_numbers = RegistrarWizardQueueAssignmentService(db).assign_same_day_queue_numbers(
            created_visits,
            target_day=today,
            source="desk",
            current_user=current_user,
        )

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

                created_visits_info.append(
                    {
                        "visit_id": visit.id,
                        "patient_name": patient_name,
                        "doctor_name": doctor_name,
                        "visit_date": visit.visit_date.isoformat(),
                        "visit_time": visit.visit_time,
                        "status": visit.status,
                        "department": visit.department,
                        "services": services_info,
                        "confirmation_required": visit.status == "pending_confirmation",
                        "confirmation_token": (
                            visit.confirmation_token
                            if visit.status == "pending_confirmation"
                            else None
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
        if queue_numbers:
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
        raise
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


def _quote_token(items: list[CartQuoteItemResponse], total_amount: Decimal, approval_status: str, quote_req: CartQuoteRequest) -> str:
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
    payload = {
        "pricing_mode": quote_req.pricing_mode,
        "discount_mode": quote_req.discount_mode,
        "all_free": bool(quote_req.all_free),
        "approval_status": approval_status,
        "items": canonical_items,
        "total_amount": str(total_amount),
    }
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
    - возвращает ВТОРОЕ значение — записанную цену за единицу для снижения
      (_recorded_unit_charge: full-update строки хранят line-total, а не
      unit-цену); квота снижения обязана токенизировать ТУ ЖЕ сумму,
      которую спишет команда (для роста это цена каталога — None);
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
    entry = edit_service._find_active_entry(
        patient_id=patient_id,
        queue_tag=queue_tag,
        target_date=target_date,
        preferred_entry_ids=item_preferred,
        specialist_id=specialist_id,
        lock=lock,
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
        resolved_specialist_id = specialist_id or service.doctor_id
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
    existing_payload = edit_service._find_service_payload(
        edit_service._coerce_services(entry.services), service
    )
    if not existing_payload:
        return requested_qty, None
    existing_qty = edit_service._payload_quantity(existing_payload)
    delta = requested_qty - existing_qty
    decrease_charge = (
        edit_service._recorded_unit_charge(
            entry=entry, payload=existing_payload, previous_qty=existing_qty
        )
        if delta < 0
        else None
    )
    return delta, decrease_charge


def _quote_core(
    db: Session,
    quote_req: CartQuoteRequest,
    lock_pricing_rows: bool = False,
    registration_settings: dict[str, Any] | None = None,
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
    # Codex R13 #3095 (P2): canonicalize duplicate service rows for the
    # full-update pricing mode. Pricing in this mode depends ONLY on
    # (service_id, quantity) — catalog rules (repeat/benefit consultation → 0,
    # all_free → 0), no custom_price / specialist input — so the same service
    # listed twice (e.g. quantities 1 and 2) and one merged row (quantity 3)
    # are the SAME priced command. full_update_online_entry merges duplicate
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
    effective_discount_mode = _resolve_effective_discount_mode(quote_req)
    # Codex R6 #3095 (P2): the save-time revalidation passes ITS OWN locked
    # settings snapshot in — quote and save are then priced from the exact
    # same values even for settings rows that do not exist yet (FOR UPDATE
    # cannot lock a row that is absent, so a concurrent admin INSERT of a
    # previously-missing key must not change the invoice after the token
    # was accepted).
    if registration_settings is None:
        registration_settings = _load_registration_discount_settings(db, lock_rows=lock_pricing_rows)

    # Codex R2 #3095 (P2): approval_status обязан отражать контракт
    # ВЫБРАННОЙ команды сохранения. RegistrarEditDeltaService._create_visit
    # всегда пишет approval_status="approved" и никогда не читает
    # all_free_auto_approve — предупреждение «требуется согласование» в
    # edit_delta-квоте вводило в заблуждение.
    # Codex R3 #3095 (P2): full-update ОБРАТНО пишет approval_status="pending"
    # для all_free (_full_update_handle_all_free_visit: и существующий
    # неоплаченный визит, и новый визит) — квота обязана предупреждать о
    # согласовании в этом случае, а не рапортовать «approved».
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
    items: list[CartQuoteItemResponse] = []

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
                .all()
            ):
                service_row_map[int(_svc.id)] = _svc

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

        # Codex R2 #3095 (P2): отклоняем отсутствие цены только когда НЕТ
        # ни одной эффективной цены. custom_price (врачебная переопределённая
        # цена) входит в контракт cart-пути сохранения — create_cart_
        # appointments использует её ПЕРЕД каталог-ценой, поэтому квота не
        # имеет права блокировать этот вызов. Для edit_delta/full_update
        # custom_price в контракте маршрута не участвует — там отсутствие
        # каталог-цены остаётся проблемой (это НЕ 0).
        if quote_req.pricing_mode == "cart":
            if service.price is None and item_req.custom_price is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Для услуги «{service.name}» не указана цена",
                )
        elif service.price is None:
            raise HTTPException(
                status_code=409,
                detail=f"Для услуги «{service.name}» не указана цена",
            )

        # Codex R1 #3095 (P1): mode 'edit_delta' повторяет ценообразование
        # RegistrarEditDeltaService один-в-один: только all_free→0,
        # custom_price и repeat/benefit скидки НЕ применяются. Это гарантирует,
        # что подтверждённая в edit-режиме сумма совпадает с тем, что
        # edit-delta реально выставит в invoice.
        if quote_req.pricing_mode == "edit_delta":
            base_price = Decimal(str(service.price))
            unit_final = Decimal("0") if effective_discount_mode == "all_free" else base_price
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
            decrease_charge: Decimal | None = None
            if quote_req.patient_id is not None and quote_req.target_date is not None:
                billable_qty, decrease_charge = _edit_delta_quote_context(
                    db,
                    service=service,
                    requested_qty=item_req.quantity,
                    patient_id=quote_req.patient_id,
                    target_date=quote_req.target_date,
                    preferred_entry_ids=set(quote_req.preferred_entry_ids),
                    specialist_id=item_req.specialist_id,
                    queue_entry_id=item_req.queue_entry_id,
                    lock=lock_pricing_rows,
                )
            else:
                billable_qty = item_req.quantity
            if billable_qty < 0 and decrease_charge is not None:
                # Снижение: команда вычитает записанную цену (не каталог);
                # квота токенизирует ровно ту же сумму за единицу.
                unit_final = decrease_charge
        elif quote_req.pricing_mode == "full_update":
            # Codex R2 #3095 (P1): зеркало _full_update_create_single_
            # independent_entry: консультация при repeat/benefit → 0,
            # all_free → 0, остальное — каталог-цена × количество.
            base_price = Decimal(str(service.price))
            if effective_discount_mode == "all_free":
                unit_final = Decimal("0")
                discount_percent = 100
            elif service.is_consultation and effective_discount_mode in ("repeat", "benefit"):
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

        final_price = (unit_final * Decimal(priced_qty)).quantize(
            Decimal("0.01")
        )
        if quote_req.pricing_mode == "full_update":
            # Codex R3 #3095 (P2): the full-update command stores
            # int(item_price) (unit × quantity) in BOTH the service payload
            # and total_amount (_full_update_create_single_independent_entry),
            # so a valid catalog price like 10.99 × 3 is saved as 32, while
            # the quote showed 32.97. Mirror the command's exact conversion:
            # the confirmed amount and the saved amount must be identical.
            final_price = Decimal(int(unit_final * Decimal(item_req.quantity)))
        total_amount += final_price

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
        approval_status=approval_status,
        quote_token=_quote_token(items, total_amount, approval_status, quote_req),
    )


@router.post("/registrar/cart/quote", response_model=CartQuoteResponse)
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
    when no token was supplied (legacy no-quote callers keep their own
    unlocked load).
    """
    if not quote_token:
        return None
    settings_snapshot = _load_registration_discount_settings(db, lock_rows=True)
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
    )
    if fresh_quote.quote_token != quote_token:
        logger.warning(
            "REGISTRATION: stale quote token — pricing changed since confirmation; "
            "current total: %s",
            fresh_quote.total_amount,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Цены или скидки изменились после подтверждения — подтвердите новую сумму. "
                f"Текущая сумма корзины: {fresh_quote.total_amount} сум"
            ),
        )
    return settings_snapshot


@router.post("/registrar/cart/edit-delta", response_model=EditDeltaResponse)
def apply_registrar_cart_edit_delta(
    request: EditDeltaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    # Codex R4 #3095 (P1): bind the confirmed edit quote to the command —
    # revalidate BEFORE any mutation (the edit-delta pricing rules are
    # mirrored by the quote's edit_delta mode; custom_price is not part of
    # the edit-delta contract).
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
    )
    try:
        result = RegistrarEditDeltaService(db).apply(
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PriceOverrideListResponse]:
    """
    Получить список изменений цен для одобрения регистратурой
    """
    try:
        query = db.query(DoctorPriceOverride).join(Service).join(Doctor)

        if status_filter != "all":
            query = query.filter(DoctorPriceOverride.status == status_filter)

        overrides = (
            query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()
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
                    doctor_name=f"Врач #{override.doctor.id}",  # Здесь нужно получить имя врача
                    doctor_specialty=override.doctor.specialty,
                    patient_name=patient_name,
                    original_price=override.original_price,
                    new_price=override.new_price,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Одобрить или отклонить изменение цены врачом
    """
    try:
        # Получаем изменение цены
        override = (
            db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == approval_data.override_id)
            .first()
        )

        if not override:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Изменение цены не найдено",
            )

        if override.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изменение цены уже обработано (статус: {override.status})",
            )

        # Обновляем статус
        if approval_data.action == "approve":
            override.status = "approved"
            override.approved_by = current_user.id
            override.approved_at = datetime.now(UTC)

            # Обновляем цену в визите
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            if visit:
                # Обновляем doctor_price_override в JSON поле
                if not visit.doctor_price_override:
                    visit.doctor_price_override = {}

                visit.doctor_price_override[str(override.service_id)] = {
                    "original_price": float(override.original_price),
                    "new_price": float(override.new_price),
                    "override_id": override.id,
                    "approved_at": override.approved_at.isoformat(),
                }

            message = "Изменение цены одобрено"

        elif approval_data.action == "reject":
            override.status = "rejected"
            override.approved_by = current_user.id
            override.approved_at = datetime.now(UTC)
            override.rejection_reason = approval_data.rejection_reason

            message = "Изменение цены отклонено"

        db.commit()
        db.refresh(override)

        return {
            "success": True,
            "message": message,
            "override_id": override.id,
            "new_status": override.status,
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


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


def _all_free_available_actions(approval_status: str) -> list[str]:
    if approval_status == "pending":
        return ["approve", "reject"]
    return []


@router.get(
    "/admin/all-free-requests", summary="Получить заявки All Free для одобрения",
    response_model=list[AllFreeVisitResponse],
)
def get_all_free_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AllFreeVisitResponse]:
    """
    Получить список заявок All Free для одобрения администратором
    """
    try:
        query = db.query(Visit).filter(Visit.discount_mode == "all_free")

        if status_filter != "all":
            query = query.filter(Visit.approval_status == status_filter)

        visits = query.order_by(Visit.created_at.desc()).limit(limit).all()

        result = []
        for visit in visits:
            available_actions = _all_free_available_actions(visit.approval_status)
            # Получаем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            total_original_amount = Decimal('0')

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    service_names.append(service.name)
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
    current_user: User = Depends(require_roles("Admin")),
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

        # Обновляем статус
        if approval_data.action == "approve":
            visit.approval_status = "approved"
            message = "Заявка All Free одобрена"

        elif approval_data.action == "reject":
            visit.approval_status = "rejected"
            # Можно добавить поле для причины отклонения в модель Visit
            if approval_data.rejection_reason:
                visit.notes = (
                    visit.notes or ""
                ) + f"\nОтклонено: {approval_data.rejection_reason}"

            message = "Заявка All Free отклонена"

        db.commit()
        db.refresh(visit)

        try:
            asyncio.run(
                notification_sender_service.send_all_free_decision_notification(
                    db=db,
                    visit=visit,
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
            "new_status": visit.approval_status,
        }

    except HTTPException:
        raise
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

