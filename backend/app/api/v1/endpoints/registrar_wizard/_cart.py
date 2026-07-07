from __future__ import annotations

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa

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
        registration_settings = _load_registration_discount_settings(db)

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


@router.post("/registrar/cart/edit-delta", response_model=EditDeltaResponse)
def apply_registrar_cart_edit_delta(
    request: EditDeltaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    try:
        result = RegistrarEditDeltaService(db).apply(
            patient_id=request.patient_id,
            services=[
                RegistrarEditDeltaItem(
                    service_id=item.service_id,
                    quantity=item.quantity,
                    specialist_id=item.specialist_id,
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
    "/registrar/price-overrides", summary="Получить все изменения цен для одобрения"
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/registrar/price-override/approve", summary="Одобрить или отклонить изменение цены"
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
    except Exception as e:
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
    "/admin/all-free-requests", summary="Получить заявки All Free для одобрения"
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/admin/all-free-approve", summary="Одобрить или отклонить заявку All Free"
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
    except Exception as e:
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

