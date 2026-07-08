"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from cashier.py (1787 LOC god file → modular).
"""
from __future__ import annotations

from app.api.v1.endpoints.cashier._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.cashier._helpers import (  # noqa: F401
    CancelPaymentRequest,
    CashierStatsResponse,
    CreateGroupedPaymentRequest,
    CreatePaymentRequest,
    GroupedPaymentAllocationItem,
    GroupedPaymentResponse,
    HourlyStatItem,
    PaginatedResponse,
    PaymentHistoryItem,
    PaymentResponse,
    PendingPaymentItem,
    RefundRequest,
    RefundResponse,
    T,
    _cashier_paid_amounts_by_visit_id,
    _cashier_payment_action_contract,
    _cashier_payment_available_amount,
    _cashier_payment_status,
    _cashier_visit_total_amount,
    _decimal_to_float,
    _emit_payment_notification,
    _preserve_cashier_visit_status,
    get_patient_name,
    router,
)


@router.get("/pending-payments", response_model=dict[str, Any])
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
    search: str | None = Query(None, description="Поиск по ФИО пациента"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
):
    """
    Получить список ожидающих оплаты записей/визитов.

    ВАЖНО: Группировка по пациенту!
    - Один пациент = одна строка (карточка) со ВСЕМИ его неоплаченными услугами
    - Полностью оплаченные пациенты НЕ показываются (они в истории платежей)
    - Если у пациента есть неоплаченные услуги - все объединяются в один блок
    """
    try:
        import math
        from collections import defaultdict

        # Базовый запрос - получаем все визиты (не отменённые и не оплаченные)
        # Исключаем визиты со статусами: canceled, paid, completed, done, closed
        excluded_statuses = CASHIER_PENDING_EXCLUDED_VISIT_STATUSES

        # ✅ ОПТИМИЗАЦИЯ: Используем joinedload для eager loading services
        # Примечание: Visit.patient relationship не существует, поэтому используем batch loading
        query = db.query(Visit).options(
            joinedload(Visit.services)
        ).filter(
            ~Visit.status.in_(excluded_statuses)
        )

        # Фильтр по датам
        if date_from:
            query = query.filter(Visit.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(Visit.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Поиск по пациенту (Join с Patient)
        if search:
            search_param = f"%{search}%"
            query = query.join(Patient, Visit.patient_id == Patient.id, isouter=True).filter(
                or_(
                    Patient.last_name.ilike(search_param),
                    Patient.first_name.ilike(search_param),
                    Patient.middle_name.ilike(search_param),
                )
            )

        # ✅ ОПТИМИЗАЦИЯ: Загружаем все визиты с eager loading для services
        all_visits = query.order_by(Visit.created_at.desc()).all()

        if not all_visits:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "size": size,
                "pages": 0
            }

        # Batch Loading: Пациенты (Visit.patient relationship не существует)
        patient_ids = list({v.patient_id for v in all_visits if v.patient_id})
        patients_map = {}
        if patient_ids:
            patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
            patients_map = {p.id: p for p in patients}

        # Batch Loading: Платежи для всех визитов (этот запрос всё ещё нужен)
        visit_ids = [v.id for v in all_visits]
        payments_map = defaultdict(list)  # visit_id -> list[Payment]
        if visit_ids:
            payments_batch = db.query(Payment).filter(
                Payment.visit_id.in_(visit_ids),
                Payment.status.in_(["paid", "completed"])
            ).all()
            for p in payments_batch:
                payments_map[p.visit_id].append(p)

        # =====================================================
        # ГРУППИРОВКА ПО ПАЦИЕНТУ
        # =====================================================
        # Структура: patient_id -> {services: [], visits: [], total, paid, remaining, ...}
        patient_groups = defaultdict(lambda: {
            "patient_id": None,
            "patient": None,
            "patient_name": "",
            "patient_iin": None,
            "visit_ids": [],
            "services": [],
            "total_amount": Decimal("0"),
            "paid_amount": Decimal("0"),
            "remaining_amount": Decimal("0"),
            "created_at": None,  # Самая ранняя дата
            "department": None,
            "queue_number": None,
        })

        for visit in all_visits:
            if not visit.patient_id:
                continue

            patient_id = visit.patient_id
            group = patient_groups[patient_id]

            # Устанавливаем данные пациента (один раз)
            if group["patient_id"] is None:
                patient = patients_map.get(patient_id)
                group["patient_id"] = patient_id
                group["patient"] = patient
                group["patient_name"] = get_patient_name(patient, patient_id)
                group["patient_iin"] = getattr(patient, 'doc_number', None) if patient else None

            # Добавляем visit_id
            group["visit_ids"].append(visit.id)

            # Самая ранняя дата создания
            if group["created_at"] is None or (visit.created_at and visit.created_at < group["created_at"]):
                group["created_at"] = visit.created_at

            # Департамент (берём первый непустой)
            if not group["department"] and hasattr(visit, 'department') and visit.department:
                group["department"] = visit.department

            # Обработка услуг визита
            if hasattr(visit, 'services') and visit.services:
                for vs in visit.services:
                    service_name = vs.name if hasattr(vs, 'name') and vs.name else "Услуга"
                    service_price = float(vs.price) if hasattr(vs, 'price') and vs.price else 0
                    service_qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1

                    group["services"].append({
                        "id": vs.service_id if hasattr(vs, 'service_id') else vs.id,
                        "visit_id": visit.id,
                        "name": service_name,
                        "price": service_price,
                        "quantity": service_qty,
                    })
                    group["total_amount"] += Decimal(str(service_price)) * service_qty

            # Оплаченная сумма для этого визита
            visit_payments = payments_map.get(visit.id, [])
            for payment in visit_payments:
                group["paid_amount"] += payment.amount

        # Считаем remaining и фильтруем оплаченных
        pending_groups = []
        for patient_id, group in patient_groups.items():  # noqa: B007  # manual-review: loop var unused but kept for API contract
            group["remaining_amount"] = group["total_amount"] - group["paid_amount"]

            # =====================================================
            # ФИЛЬТРАЦИЯ: Исключаем полностью оплаченных
            # =====================================================

            # 1. Если нет услуг - пропускаем
            if not group["services"]:
                continue

            # 2. Если total_amount = 0 (нет цены у услуг) - считаем бесплатным, пропускаем
            if group["total_amount"] <= 0:
                continue

            # 3. Если remaining_amount <= 0 - полностью оплачено, пропускаем
            if group["remaining_amount"] <= 0:
                continue

            # 4. Если paid >= total - полностью оплачено, пропускаем
            if group["paid_amount"] >= group["total_amount"]:
                continue

            # Определяем статус для неоплаченных
            if group["paid_amount"] > 0:
                group["status"] = "partial"  # Частично оплачено
            else:
                group["status"] = "pending"  # Ожидает оплаты

            pending_groups.append(group)

        # Сортируем группы по дате создания (новые сверху)
        pending_groups.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)

        # Подсчёт общего количества (до пагинации)
        total_count = len(pending_groups)

        # Пагинация
        offset = (page - 1) * size
        paginated_groups = pending_groups[offset:offset + size]

        # Формируем результат
        result = []
        for group in paginated_groups:
            group_visit_ids = group["visit_ids"]
            direct_payment_allowed = len(group_visit_ids) == 1
            result.append(PendingPaymentItem(
                id=group["visit_ids"][0] if group["visit_ids"] else 0,  # Первый visit_id для совместимости
                patient_id=group["patient_id"],
                patient_name=group["patient_name"],
                patient_iin=group["patient_iin"],
                visit_id=group["visit_ids"][0] if group["visit_ids"] else None,
                visit_ids=group["visit_ids"],  # Все visit_id пациента
                appointment_id=None,
                services=group["services"],
                total_amount=group["total_amount"],
                paid_amount=group["paid_amount"],
                remaining_amount=group["remaining_amount"],
                status=group["status"],
                created_at=group["created_at"],
                queue_number=group["queue_number"],
                department=group["department"],
                payment_contract="single_visit" if direct_payment_allowed else "grouped_visits",
                payment_visit_id=group_visit_ids[0] if direct_payment_allowed else None,
                payment_visit_ids=group_visit_ids,
                can_create_direct_payment=direct_payment_allowed,
                can_create_grouped_payment=not direct_payment_allowed,
            ))

        return {
            "items": result,
            "total": total_count,
            "page": page,
            "size": size,
            "pages": math.ceil(total_count / size) if size > 0 else 0
        }

    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )



@router.get("/payments", response_model=PaginatedResponse[PaymentHistoryItem])
async def get_payments(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
    date_from: date | None = Query(None, description="Дата начала"),
    date_to: date | None = Query(None, description="Дата окончания"),
    search: str | None = Query(None, description="Поиск по пациенту"),
    status_filter: str | None = Query(None, alias="status", description="Фильтр по статусу (paid/pending/cancelled)"),
    method: str | None = Query(None, description="Фильтр по методу оплаты (cash/card)"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
):
    """
    Получить историю платежей с пагинацией и поиском.
    """
    try:
        query = db.query(Payment)

        # Фильтр по статусу
        if status_filter:
            query = query.filter(Payment.status == status_filter)

        # Фильтр по методу оплаты
        if method:
            query = query.filter(Payment.method == method)

        # Join необходимы для поиска по имени пациента
        if search:
            # Payment -> Visit -> Patient
            query = query.join(Visit, Payment.visit_id == Visit.id)\
                         .join(Patient, Visit.patient_id == Patient.id)

            search_param = f"%{search}%"
            query = query.filter(
                or_(
                    Patient.last_name.ilike(search_param),
                    Patient.first_name.ilike(search_param),
                    Patient.middle_name.ilike(search_param),
                )
            )

        # Фильтр по датам
        if date_from:
            # При поиске может быть join, поэтому явно указываем Payment.created_at
            query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))

        # Получаем общее количество ДО пагинации
        total_count = query.count()

        # Пагинация и Сортировка
        offset = (page - 1) * size
        query = query.order_by(Payment.created_at.desc()).offset(offset).limit(size)

        payments = query.all()

        # === Batch Loading Optimization ===
        visit_ids = [p.visit_id for p in payments if p.visit_id]
        visits_map = {}
        patients_map = {}

        if visit_ids:
            visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
            visits_map = {v.id: v for v in visits}

            patient_ids = [v.patient_id for v in visits if v.patient_id]
            if patient_ids:
                patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
                patients_map = {p.id: p for p in patients}

        items = []
        for payment in payments:
            patient_id = 0
            patient_name = "Неизвестно"

            if payment.visit_id:
                visit = visits_map.get(payment.visit_id)
                if visit:
                    patient_id = visit.patient_id
                    patient = patients_map.get(visit.patient_id)
                    patient_name = get_patient_name(patient, visit.patient_id)

            items.append(PaymentHistoryItem(
                id=payment.id,
                patient_id=patient_id,
                patient_name=patient_name,
                visit_id=payment.visit_id,
                amount=payment.amount,
                method=payment.method if hasattr(payment, 'method') else 'cash',
                status=payment.status,
                created_at=payment.created_at,
                paid_at=payment.paid_at if hasattr(payment, 'paid_at') else None,
                note=payment.note if hasattr(payment, 'note') else None,
                cashier_name=None,
                **_cashier_payment_action_contract(payment),
            ))

        import math
        return PaginatedResponse(
            items=items,
            total=total_count,
            page=page,
            size=size,
            pages=math.ceil(total_count / size) if size > 0 else 0
        )

    except Exception:
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/payments/grouped", response_model=GroupedPaymentResponse)
async def create_grouped_payment(
    payment_data: CreateGroupedPaymentRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Create cashier payments for a grouped pending-payment row.

    Allocation is backend-owned: visits must belong to one patient, amount is
    allocated oldest visit first by remaining backend-calculated debt, and
    overpay is rejected instead of being assigned to an arbitrary visit.
    """
    normalized_visit_ids = list(dict.fromkeys(payment_data.visit_ids))
    if not normalized_visit_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="visit_ids is required",
        )

    visits = db.query(Visit).options(joinedload(Visit.services)).filter(
        Visit.id.in_(normalized_visit_ids)
    ).all()
    visits_by_id = {visit.id: visit for visit in visits}
    missing_visit_ids = [visit_id for visit_id in normalized_visit_ids if visit_id not in visits_by_id]
    if missing_visit_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visits not found: {missing_visit_ids}",
        )

    patient_ids = {visit.patient_id for visit in visits if visit.patient_id is not None}
    if len(patient_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grouped cashier payment requires visits from exactly one patient",
        )

    patient_id = next(iter(patient_ids))
    if payment_data.patient_id is not None and payment_data.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grouped cashier payment patient_id does not match visit ownership",
        )

    paid_amounts = _cashier_paid_amounts_by_visit_id(db, normalized_visit_ids)
    allocation_candidates = []
    for visit in visits:
        total_amount = _cashier_visit_total_amount(visit)
        paid_amount = paid_amounts.get(visit.id, Decimal("0"))
        remaining_amount = total_amount - paid_amount
        if remaining_amount > 0:
            allocation_candidates.append({
                "visit": visit,
                "remaining_amount": remaining_amount,
            })

    allocation_candidates.sort(
        key=lambda item: (
            item["visit"].created_at or datetime.min,
            item["visit"].id,
        )
    )

    total_remaining = sum(
        (item["remaining_amount"] for item in allocation_candidates),
        Decimal("0"),
    )
    if total_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grouped cashier payment has no remaining backend-calculated debt",
        )
    if payment_data.amount > total_remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grouped cashier payment amount exceeds backend-calculated remaining debt",
        )

    remaining_to_allocate = payment_data.amount
    created_at = datetime.now(UTC)
    created_payments: list[Payment] = []
    allocation_rows: list[tuple[Payment, Visit, Decimal, Decimal, Decimal]] = []

    try:
        for candidate in allocation_candidates:
            if remaining_to_allocate <= 0:
                break

            visit = candidate["visit"]
            remaining_before = candidate["remaining_amount"]
            allocation_amount = min(remaining_to_allocate, remaining_before)
            if allocation_amount <= 0:
                continue

            payment = Payment(
                visit_id=visit.id,
                amount=allocation_amount,
                method=payment_data.method,
                status="paid",
                note=payment_data.note,
                created_at=created_at,
                paid_at=created_at,
            )
            db.add(payment)
            db.flush()

            remaining_after = remaining_before - allocation_amount
            created_payments.append(payment)
            allocation_rows.append((
                payment,
                visit,
                allocation_amount,
                remaining_before,
                remaining_after,
            ))
            remaining_to_allocate -= allocation_amount

        if remaining_to_allocate != Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Grouped cashier payment could not allocate full amount",
            )

        db.commit()
        for payment in created_payments:
            db.refresh(payment)

        for payment, visit, *_ in allocation_rows:
            await _emit_payment_notification(
                db=db,
                payment=payment,
                current_user=current_user,
                change_type="paid",
                patient_id=patient_id,
                visit=visit,
            )

        try:
            import asyncio

            from app.ws.cashier_ws import broadcast_cashier_update

            for payment in created_payments:
                asyncio.create_task(broadcast_cashier_update("payment_created", {
                    "payment_id": payment.id,
                    "visit_id": payment.visit_id,
                    "patient_id": patient_id,
                    "amount": float(payment.amount),
                    "method": payment.method,
                    "status": payment.status,
                }))
        except Exception as ws_error:
            logger.warning(f"WebSocket broadcast failed: {ws_error}")

        return GroupedPaymentResponse(
            patient_id=patient_id,
            amount=payment_data.amount,
            method=payment_data.method,
            status="paid",
            created_at=created_at,
            payments=[
                PaymentResponse(
                    id=payment.id,
                    visit_id=payment.visit_id,
                    patient_id=patient_id,
                    amount=payment.amount,
                    method=payment.method,
                    status=payment.status,
                    created_at=payment.created_at,
                    paid_at=payment.paid_at,
                    note=payment.note,
                )
                for payment in created_payments
            ],
            allocations=[
                GroupedPaymentAllocationItem(
                    visit_id=visit.id,
                    payment_id=payment.id,
                    amount=allocation_amount,
                    remaining_before=remaining_before,
                    remaining_after=remaining_after,
                )
                for payment, visit, allocation_amount, remaining_before, remaining_after in allocation_rows
            ],
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Grouped cashier payment allocation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grouped cashier payment allocation failed: {str(exc)}",
        )


@router.post("/payments", response_model=PaymentResponse)
async def create_payment(
    payment_data: CreatePaymentRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Создать новый платеж.
    """
    try:
        # Определяем patient_id
        patient_id = payment_data.patient_id
        visit = None

        if payment_data.visit_id:
            def _ensure_appointment_matches_visit() -> None:
                if not payment_data.appointment_id:
                    return
                if not visit:
                    return
                try:
                    resolved_visit_id = CanonicalVisitService(db).resolve_canonical_visit(
                        payment_data.appointment_id,
                        create_if_missing=False,
                    )
                except CanonicalVisitResolutionError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="appointment_id does not match visit_id",
                    ) from exc
                if resolved_visit_id != visit.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="appointment_id does not match visit_id",
                    )

            # ✅ FIX: Use lazy load to ensure consistency with get_pending_payments
            visit = db.query(Visit).filter(Visit.id == payment_data.visit_id).first()
            _ensure_appointment_matches_visit()
            if not visit:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Визит не найден"
                )
            if (
                payment_data.patient_id is not None
                and visit.patient_id != payment_data.patient_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cashier payment patient_id does not match visit ownership",
                )
            patient_id = visit.patient_id

            # === ВАЛИДАЦИЯ ПЕРЕПЛАТЫ ===
            # 1. Считаем общую стоимость услуг
            total_cost = Decimal("0")
            if hasattr(visit, 'services') and visit.services:
                for vs in visit.services:
                    price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                    qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                    total_cost += price * qty

            # Fallback: если услуги не загружены, используем visit.total_price (если есть)
            if total_cost == Decimal("0"):
                if hasattr(visit, 'total_price') and visit.total_price:
                    total_cost = Decimal(str(visit.total_price))
                elif hasattr(visit, 'total_amount') and visit.total_amount:
                    total_cost = Decimal(str(visit.total_amount))

            # 2. Считаем уже оплаченное
            paid_amount = Decimal("0")
            existing_payments = db.query(Payment).filter(
                Payment.visit_id == visit.id,
                Payment.status.in_(["paid", "completed"])
            ).all()
            for p in existing_payments:
                paid_amount += p.amount

            # 3. Проверяем остаток
            remaining_debt = total_cost - paid_amount

            # === ВАЛИДАЦИЯ ПЕРЕПЛАТЫ С AUDIT-TRAIL ===
            # Кассир может принять сумму, превышающую остаток (аванс/депозит),
            # но это должно быть явно залогировано для финансового аудита.
            try:
                payment_amount_decimal = Decimal(str(payment_data.amount))
            except (ArithmeticError, ValueError):
                payment_amount_decimal = Decimal("0")

            overpayment_amount = payment_amount_decimal - remaining_debt
            if overpayment_amount > Decimal("0"):
                # Авансовый платёж/переплата: разрешаем, но записываем в audit log.
                logger.warning(
                    "Cashier overpayment accepted: visit_id=%s patient_id=%s "
                    "total_cost=%s paid_amount=%s remaining_debt=%s "
                    "payment_amount=%s overpayment=%s cashier_id=%s",
                    visit.id,
                    patient_id,
                    str(total_cost),
                    str(paid_amount),
                    str(remaining_debt),
                    str(payment_amount_decimal),
                    str(overpayment_amount),
                    getattr(current_user, "id", None),
                )

            # Запрещаем приём платежа, когда услуги уже полностью оплачены
            # и кассир пытается принять ещё один (без явного намерения аванса).
            if remaining_debt <= Decimal("0") and payment_amount_decimal > Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Все услуги уже оплачены. "
                        "Приём дополнительного платежа невозможен без авансового договора."
                    ),
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для создания платежа необходимо указать visit_id"
            )

        # Создаем платеж
        new_payment = Payment(
            visit_id=payment_data.visit_id,
            amount=payment_data.amount,
            method=payment_data.method,
            status="paid",
            note=payment_data.note,
            created_at=datetime.now(UTC),
            paid_at=datetime.now(UTC),
        )

        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        await _emit_payment_notification(
            db=db,
            payment=new_payment,
            current_user=current_user,
            change_type="paid",
            patient_id=patient_id,
            visit=visit,
        )

        # 🔔 WebSocket: Broadcast payment_created event
        try:
            import asyncio

            from app.ws.cashier_ws import broadcast_cashier_update
            asyncio.create_task(broadcast_cashier_update("payment_created", {
                "payment_id": new_payment.id,
                "visit_id": new_payment.visit_id,
                "patient_id": patient_id,
                "amount": float(new_payment.amount),
                "method": new_payment.method,
                "status": new_payment.status
            }))
        except Exception as ws_error:
            logger.warning(f"WebSocket broadcast failed: {ws_error}")

        return PaymentResponse(
            id=new_payment.id,
            visit_id=new_payment.visit_id,
            patient_id=patient_id,
            amount=new_payment.amount,
            method=new_payment.method,
            status=new_payment.status,
            created_at=new_payment.created_at,
            paid_at=new_payment.paid_at,
            note=new_payment.note,
        )

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment_by_id(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Получить платеж по ID.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Платеж не найден"
        )

    # Определяем patient_id через visit
    patient_id = None
    if payment.visit_id:
        visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
        if visit:
            patient_id = visit.patient_id

    return PaymentResponse(
        id=payment.id,
        visit_id=payment.visit_id,
        patient_id=patient_id,
        amount=payment.amount,
        method=payment.method if hasattr(payment, 'method') else 'cash',
        status=payment.status,
        created_at=payment.created_at,
        paid_at=payment.paid_at if hasattr(payment, 'paid_at') else None,
        note=payment.note if hasattr(payment, 'note') else None,
    )


@router.post("/payments/{payment_id}/cancel", response_model=dict[str, Any])
async def cancel_payment(
    payment_id: int,
    cancel_data: CancelPaymentRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Отменить платеж.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Платеж не найден"
        )

    if _cashier_payment_status(payment) in {"cancelled", "refunded", "void"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Платеж уже отменен"
        )

    try:
        # Отменяем платеж
        payment.status = "cancelled"
        if hasattr(payment, 'note') and cancel_data.reason:
            payment.note = f"Отменён: {cancel_data.reason}"

        # Возвращаем только operational статус визита; registration type не трогаем.
        visit = None
        if payment.visit_id:
            visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
            if visit and visit.status == 'paid':
                visit.status = _preserve_cashier_visit_status(visit.status)
                db.add(visit)

        db.commit()

        await _emit_payment_notification(
            db=db,
            payment=payment,
            current_user=current_user,
            change_type="cancelled",
            patient_id=visit.patient_id if visit else None,
            visit=visit,
            reason=cancel_data.reason,
        )

        return {
            "success": True,
            "message": "Платеж успешно отменен",
            "payment_id": payment_id
        }

    except Exception:
        db.rollback()
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/payments/{payment_id}/confirm", response_model=dict[str, Any])
async def confirm_payment(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Вручную подтвердить платеж.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
         raise HTTPException(status_code=404, detail="Платеж не найден")

    payment_status = _cashier_payment_status(payment)

    if payment_status in {'paid', 'completed'}:
         return {"success": True, "message": "Платеж уже оплачен"}

    if payment_status in {'cancelled', 'refunded', 'void'}:
         raise HTTPException(status_code=400, detail="Нельзя подтвердить отмененный платеж")

    # Обновляем статус платежа
    payment.status = 'paid'
    if not payment.provider_transaction_id:
        from datetime import datetime
        payment.provider_transaction_id = f"MANUAL-{payment_id}-{int(datetime.now(UTC).timestamp())}"

    # Обновляем только operational статус визита; registration type не меняем.
    visit = None
    if payment.visit_id:
         visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
         if visit:
              visit.status = _preserve_cashier_visit_status(visit.status)
              db.add(visit)

    db.commit()
    await _emit_payment_notification(
        db=db,
        payment=payment,
        current_user=current_user,
        change_type="paid_manual",
        patient_id=visit.patient_id if visit else None,
        visit=visit,
        extra_metadata={"confirmation_mode": "manual"},
    )
    return {"success": True, "status": "paid"}


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def refund_payment(
    payment_id: int,
    refund_data: RefundRequest,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.require_roles("Admin", "Cashier")),
):
    """
    Частичный или полный возврат средств по платежу.
    """
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Платеж не найден"
            )

        if payment.status not in ["paid", "completed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Невозможно выполнить возврат для платежа со статусом '{payment.status}'"
            )

        # Atomic refund: use SQL UPDATE with WHERE guard to prevent race condition.
        # Two concurrent requests could both read refunded_amount=0 and both pass
        # the available_for_refund check. This atomic UPDATE ensures only one wins.
        from sqlalchemy import text as sql_text

        refund_amount_decimal = Decimal(str(refund_data.amount))
        atomic_update = sql_text("""
            UPDATE payments
            SET refunded_amount = COALESCE(refunded_amount, 0) + :refund_amount,
                refund_reason = :reason,
                refunded_at = :now,
                refunded_by = :user_id
            WHERE id = :payment_id
              AND COALESCE(refunded_amount, 0) + :refund_amount <= amount
        """)
        result = db.execute(atomic_update, {
            "refund_amount": refund_amount_decimal,
            "reason": refund_data.reason,
            "now": datetime.now(UTC),
            "user_id": current_user.id if hasattr(current_user, 'id') else None,
            "payment_id": payment_id,
        })

        if result.rowcount == 0:
            # Either payment doesn't exist or refund would exceed amount (race lost)
            db.rollback()
            already_refunded = payment.refunded_amount or Decimal("0")
            available = payment.amount - already_refunded
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Сумма возврата ({refund_data.amount}) превышает доступную ({available}). Возможно, возврат уже был выполнен."
            )

        db.commit()
        db.refresh(payment)

        new_refunded_amount = payment.refunded_amount or Decimal("0")

        # PAY-REAUDIT-28 P0-4: вызываем API провайдера для фактического возврата
        # средств. Раньше локальные проводки обновлялись, но деньги оставались
        # у провайдера (Click/PayMe/Kaspi). Пациент не получал возврат.
        if payment.provider and payment.provider_payment_id:
            try:
                from app.services.payment_provider_manager_factory import (
                    get_payment_manager,
                )
                _manager = get_payment_manager()
                _refund_result = _manager.refund_payment(
                    payment.provider,
                    payment.provider_payment_id,
                    refund_amount_decimal,
                )
                if not _refund_result or not getattr(_refund_result, "success", False):
                    # Откатываем локальный UPDATE — деньги у провайдера не вернулись.
                    db.rollback()
                    # Перезагружаем payment из БД (после rollback)
                    db.refresh(payment)
                    _err = getattr(_refund_result, "error_message", "Unknown provider error") if _refund_result else "Provider refund returned None"
                    logger.error(
                        "Provider refund failed for payment_id=%s provider=%s: %s",
                        payment_id, payment.provider, _err,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Провайдер отклонил возврат: {_err}. Локальные проводки откачены, статус платежа не изменён.",
                    )
            except HTTPException:
                raise
            except Exception as prov_err:
                # Если провайдер недоступен/не реализует refund — откатываем локал.
                db.rollback()
                db.refresh(payment)
                logger.exception(
                    "Provider refund call raised for payment_id=%s provider=%s",
                    payment_id, payment.provider,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Не удалось выполнить возврат через провайдера: {type(prov_err).__name__}. Локальные проводки откачены.",
                )

        # Если возвращена вся сумма — статус "refunded"
        if new_refunded_amount >= payment.amount:
            payment.status = "refunded"

            # Возвращаем только operational статус при полном возврате.
            if payment.visit_id:
                visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
                if visit and visit.status == 'paid':
                    visit.status = _preserve_cashier_visit_status(visit.status)
                    db.add(visit)
            db.commit()
            db.refresh(payment)

        refund_change_type = "full_refund" if payment.status == "refunded" else "partial_refund"
        refund_visit = db.query(Visit).filter(Visit.id == payment.visit_id).first() if payment.visit_id else None
        await _emit_payment_notification(
            db=db,
            payment=payment,
            current_user=current_user,
            change_type=refund_change_type,
            patient_id=refund_visit.patient_id if refund_visit else None,
            visit=refund_visit,
            reason=refund_data.reason,
            extra_metadata={
                "refund_amount": _decimal_to_float(refund_data.amount),
                "remaining_amount": _decimal_to_float(payment.amount - new_refunded_amount),
            },
        )

        return RefundResponse(
            id=payment.id,
            original_amount=payment.amount,
            refunded_amount=new_refunded_amount,
            remaining_amount=payment.amount - new_refunded_amount,
            reason=refund_data.reason,
            refunded_at=payment.refunded_at,
            status=payment.status
        )

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Unhandled cashier endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ===================== ПЕЧАТЬ ЧЕКА =====================


