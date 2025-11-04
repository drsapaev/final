"""
API endpoints для мастера регистрации с поддержкой корзины
Расширение существующего registrar_integration.py
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.clinic import Doctor, ClinicSettings
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.doctor_price_override import DoctorPriceOverride
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
from app.services.feature_flags import is_feature_enabled

router = APIRouter()

# ===================== СХЕМЫ ДЛЯ КОРЗИНЫ =====================

class ServiceItemRequest(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1)
    custom_price: Optional[Decimal] = None  # Для врачебного переопределения цены

class VisitRequest(BaseModel):
    doctor_id: Optional[int] = None  # Может быть None для лабораторных услуг
    services: List[ServiceItemRequest]
    visit_date: date
    visit_time: Optional[str] = None  # HH:MM
    department: Optional[str] = None
    notes: Optional[str] = None

class CartRequest(BaseModel):
    patient_id: int
    visits: List[VisitRequest]
    discount_mode: str = Field(default="none")  # none|repeat|benefit|all_free
    payment_method: str = Field(default="cash")  # cash|card|online|click|payme
    all_free: bool = Field(default=False)  # Чекбокс "All Free"
    notes: Optional[str] = None

class CartResponse(BaseModel):
    success: bool
    message: str
    invoice_id: int
    visit_ids: List[int]
    total_amount: Decimal
    queue_numbers: Dict[int, List[Dict]]  # visit_id -> [{"queue_tag": str, "number": int, "queue_id": int}]
    print_tickets: List[Dict[str, Any]]
    created_visits: Optional[List[Dict[str, Any]]] = None  # Информация о созданных визитах

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def _check_repeat_visit_eligibility(
    db: Session, 
    patient_id: int, 
    doctor_id: int, 
    service_ids: List[int]
) -> bool:
    """
    Проверка права на повторный визит (≤21 день у того же специалиста)
    """
    # Получаем консультации этого врача за последние 21 день
    cutoff_date = date.today() - timedelta(days=21)
    
    recent_visits = db.query(Visit).filter(
        Visit.patient_id == patient_id,
        Visit.doctor_id == doctor_id,
        Visit.visit_date >= cutoff_date,
        Visit.status != "cancelled"
    ).all()
    
    if not recent_visits:
        return False
    
    # Проверяем, есть ли среди выбранных услуг консультации
    consultation_services = db.query(Service).filter(
        Service.id.in_(service_ids),
        Service.is_consultation == True
    ).all()
    
    return len(consultation_services) > 0

def _calculate_visit_price(
    db: Session,
    services: List[ServiceItemRequest],
    discount_mode: str,
    patient_id: int,
    doctor_id: Optional[int]
) -> Decimal:
    """
    Расчёт цены визита с учётом льгот и скидок
    """
    total = Decimal('0')
    
    for service_item in services:
        service = db.query(Service).filter(Service.id == service_item.service_id).first()
        if not service:
            continue
            
        # Базовая цена (кастомная или из справочника)
        base_price = service_item.custom_price or service.price or Decimal('0')
        item_total = base_price * service_item.quantity
        
        # Применяем скидки
        if discount_mode == "repeat" and service.is_consultation:
            # Повторная консультация бесплатна
            item_total = Decimal('0')
        elif discount_mode == "benefit" and service.is_consultation:
            # Льготная консультация бесплатна
            item_total = Decimal('0')
        elif discount_mode == "all_free":
            # Всё бесплатно (требует одобрения)
            item_total = Decimal('0')
        
        total += item_total
    
    return total

def _create_queue_entries(
    db: Session,
    visits: List[Visit],
    queue_settings: Dict[str, Any]
) -> Dict[int, int]:
    """
    Создание записей в очереди для визитов на сегодня
    """
    queue_numbers = {}
    today = date.today()
    
    for visit in visits:
        if visit.visit_date != today:
            continue
            
        # Определяем все уникальные типы очередей для услуг визита
        visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        service_ids = [vs.service_id for vs in visit_services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()
        
        # Собираем все уникальные queue_tag для создания отдельных очередей
        unique_queue_tags = set()
        for service in services:
            if service.queue_tag:
                unique_queue_tags.add(service.queue_tag)
            else:
                unique_queue_tags.add("general")  # По умолчанию
        
        # Создаём отдельную запись в очереди для каждого типа услуг
        visit_queue_numbers = []
        try:
            for queue_tag in unique_queue_tags:
                # Определяем врача для очереди
                doctor_id = visit.doctor_id
                
                # Для очередей без конкретного врача используем ресурс-врачей
                if queue_tag == "ecg" and not doctor_id:
                    # Ищем ресурс-врача ЭКГ
                    from app.models.user import User
                    ecg_resource = db.query(User).filter(
                        User.username == "ecg_resource",
                        User.is_active == True
                    ).first()
                    if ecg_resource:
                        doctor_id = ecg_resource.id
                    else:
                        print(f"Warning: ЭКГ ресурс-врач не найден для queue_tag={queue_tag}")
                        continue
                        
                elif queue_tag == "lab" and not doctor_id:
                    # Ищем ресурс-врача лаборатории
                    from app.models.user import User
                    lab_resource = db.query(User).filter(
                        User.username == "lab_resource",
                        User.is_active == True
                    ).first()
                    if lab_resource:
                        doctor_id = lab_resource.id
                    else:
                        print(f"Warning: Лаборатория ресурс-врач не найден для queue_tag={queue_tag}")
                        continue
                
                daily_queue = crud_queue.get_or_create_daily_queue(
                    db, today, doctor_id, queue_tag
                )
                
                # Вычисляем номер
                current_count = crud_queue.count_queue_entries(db, daily_queue.id)
                start_number = queue_settings.get("start_numbers", {}).get(queue_tag, 1)
                next_number = start_number + current_count
                
                # Создаём запись
                queue_entry = crud_queue.create_queue_entry(
                    db, 
                    queue_id=daily_queue.id,
                    patient_id=visit.patient_id,
                    number=next_number,
                    source="desk"
                )
                
                visit_queue_numbers.append({
                    "queue_tag": queue_tag,
                    "number": next_number,
                    "queue_id": daily_queue.id
                })
            
            # Сохраняем все номера очередей для визита
            queue_numbers[visit.id] = visit_queue_numbers
            
        except Exception as e:
            print(f"Warning: Could not create queue entries for visit {visit.id}: {e}")
    
    return queue_numbers

# ===================== CLICK ИНТЕГРАЦИЯ =====================

class InvoicePaymentRequest(BaseModel):
    invoice_id: int
    provider: str = Field(default="click")  # click|payme
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None

class InvoicePaymentResponse(BaseModel):
    success: bool
    payment_url: Optional[str] = None
    provider_payment_id: Optional[str] = None
    error_message: Optional[str] = None

@router.post("/registrar/invoice/init-payment", response_model=InvoicePaymentResponse)
def init_invoice_payment(
    payment_req: InvoicePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Инициация оплаты для invoice через Click/PayMe
    """
    try:
        # Получаем invoice
        invoice = db.query(PaymentInvoice).filter(PaymentInvoice.id == payment_req.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")
        
        if invoice.status != "pending":
            raise HTTPException(status_code=400, detail=f"Invoice уже обработан: {invoice.status}")
        
        # Инициализируем провайдер платежей
        if payment_req.provider == "click":
            from app.services.payment_providers.click import ClickProvider
            
            # Конфигурация Click (в реальном проекте из настроек)
            provider_config = {
                "service_id": "test_service",
                "merchant_id": "test_merchant", 
                "secret_key": "test_secret",
                "base_url": "https://api.click.uz/v2"
            }
            
            provider = ClickProvider(provider_config)
            
        elif payment_req.provider == "payme":
            from app.services.payment_providers.payme import PayMeProvider
            
            # Конфигурация PayMe (в реальном проекте из настроек)
            provider_config = {
                "merchant_id": "test_merchant_payme",
                "secret_key": "test_secret_payme",
                "base_url": "https://checkout.paycom.uz",
                "api_url": "https://api.paycom.uz"
            }
            
            provider = PayMeProvider(provider_config)
            
        else:
            return InvoicePaymentResponse(
                success=False,
                error_message=f"Провайдер {payment_req.provider} не поддерживается"
            )
        
        # Создаём платёж
        result = provider.create_payment(
            amount=invoice.total_amount,
            currency=invoice.currency,
            order_id=f"invoice_{invoice.id}",
            description=f"Оплата визитов #{invoice.id}",
            return_url=payment_req.return_url,
            cancel_url=payment_req.cancel_url
        )
        
        if result.success:
            # Обновляем invoice
            invoice.provider_payment_id = result.payment_id
            invoice.payment_method = payment_req.provider
            invoice.provider = payment_req.provider
            invoice.status = "processing"
            invoice.provider_data = result.provider_data
            db.commit()
            
            return InvoicePaymentResponse(
                success=True,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id
            )
        else:
            return InvoicePaymentResponse(
                success=False,
                error_message=result.error_message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка инициации платежа: {str(e)}"
        )

@router.get("/registrar/invoice/{invoice_id}/status")
def check_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Проверка статуса оплаты invoice
    """
    try:
        invoice = db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")
        
        # Если статус уже финальный, возвращаем как есть
        if invoice.status in ["paid", "failed", "cancelled"]:
            return {
                "invoice_id": invoice.id,
                "status": invoice.status,
                "total_amount": invoice.total_amount,
                "currency": invoice.currency,
                "provider_payment_id": invoice.provider_payment_id
            }
        
        # Проверяем статус у провайдера
        if invoice.provider_payment_id and invoice.provider:
            provider = None
            
            if invoice.provider == "click":
                from app.services.payment_providers.click import ClickProvider
                
                provider_config = {
                    "service_id": "test_service",
                    "merchant_id": "test_merchant",
                    "secret_key": "test_secret",
                    "base_url": "https://api.click.uz/v2"
                }
                
                provider = ClickProvider(provider_config)
                
            elif invoice.provider == "payme":
                from app.services.payment_providers.payme import PayMeProvider
                
                provider_config = {
                    "merchant_id": "test_merchant_payme",
                    "secret_key": "test_secret_payme",
                    "base_url": "https://checkout.paycom.uz",
                    "api_url": "https://api.paycom.uz"
                }
                
                provider = PayMeProvider(provider_config)
            
            if provider:
                result = provider.check_payment_status(invoice.provider_payment_id)
                
                if result.success:
                    # Обновляем статус invoice
                    if result.status == "completed":
                        invoice.status = "paid"
                        invoice.paid_at = datetime.utcnow()
                        
                        # Помечаем все визиты как оплаченные
                        invoice_visits = db.query(PaymentInvoiceVisit).filter(
                            PaymentInvoiceVisit.invoice_id == invoice.id
                        ).all()
                        
                        for iv in invoice_visits:
                            visit = db.query(Visit).filter(Visit.id == iv.visit_id).first()
                            if visit:
                                visit.status = "confirmed"  # Оплачено и подтверждено
                        
                        db.commit()
                    elif result.status in ["failed", "cancelled"]:
                        invoice.status = result.status
                        db.commit()
        
        return {
            "invoice_id": invoice.id,
            "status": invoice.status,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "provider_payment_id": invoice.provider_payment_id,
            "paid_at": invoice.paid_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки статуса: {str(e)}"
        )

# ===================== ОСНОВНОЙ ENDPOINT =====================

@router.post("/registrar/cart", response_model=CartResponse)
def create_cart_appointments(
    cart_data: CartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Создание корзины визитов с единым платежом
    Поддерживает: повторные/льготные визиты, All Free, динамические цены, очереди по queue_tag
    """
    print(f"📥 REGISTRATION DEBUG: Получен запрос на создание корзины")
    print(f"   Patient ID: {cart_data.patient_id}")
    print(f"   Количество визитов: {len(cart_data.visits)}")
    print(f"   Discount mode: {cart_data.discount_mode}")
    print(f"   Payment method: {cart_data.payment_method}")

    try:
        # Валидация пациента
        # (Предполагаем, что пациент уже существует, так как он выбран в мастере)
        
        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)
        
        created_visits = []
        total_invoice_amount = Decimal('0')
        
        # Создаём визиты
        from time import sleep
        print(f"📋 REGISTRATION DEBUG: Создаём {len(cart_data.visits)} визитов")
        for idx, visit_req in enumerate(cart_data.visits):
            print(f"   Визит {idx+1}: department={visit_req.department}, services={len(visit_req.services)}")
            # Проверяем право на повторный визит
            if cart_data.discount_mode == "repeat" and visit_req.doctor_id:
                service_ids = [s.service_id for s in visit_req.services]
                if not _check_repeat_visit_eligibility(
                    db, cart_data.patient_id, visit_req.doctor_id, service_ids
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Повторный визит недоступен: нет консультации у этого врача за последние 21 день"
                    )
            
            # Рассчитываем цену визита
            visit_amount = _calculate_visit_price(
                db, visit_req.services, cart_data.discount_mode, 
                cart_data.patient_id, visit_req.doctor_id
            )
            
            # ✅ ИСПРАВЛЕНО: Регистратор всегда создаёт подтверждённые записи
            # Фича-флаг "confirmation_before_queue" применяется только для онлайн-записей (телеграм/PWA)
            # Записи от регистратора сразу попадают в очередь
            visit_status = "confirmed"
            confirmed_at = datetime.utcnow()
            confirmed_by = f"registrar_{current_user.id}"
            
            # ✅ ИСПРАВЛЕНО: Добавляем микрозадержку для разных created_at
            # Это гарантирует, что визиты одного пациента будут иметь разные временные метки
            if idx > 0:
                sleep(0.001)  # 1 миллисекунда задержки между визитами
            
            # Создаём визит
            visit = Visit(
                patient_id=cart_data.patient_id,
                doctor_id=visit_req.doctor_id,
                visit_date=visit_req.visit_date,
                visit_time=visit_req.visit_time,
                department=visit_req.department,
                notes=visit_req.notes,
                status=visit_status,
                discount_mode=cart_data.discount_mode,
                approval_status="approved" if cart_data.discount_mode != "all_free" else "pending",
                confirmed_at=confirmed_at,
                confirmed_by=confirmed_by
            )
            db.add(visit)
            db.flush()  # Получаем ID визита
            print(f"✅ REGISTRATION DEBUG: Визит {visit.id} добавлен в сессию")
            
            # Добавляем услуги к визиту
            for service_item in visit_req.services:
                service = db.query(Service).filter(Service.id == service_item.service_id).first()
                if not service:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Услуга с ID {service_item.service_id} не найдена"
                    )
                
                # Цена с учётом скидок
                if cart_data.discount_mode == "all_free":
                    item_price = Decimal('0')
                elif cart_data.discount_mode in ["repeat", "benefit"] and service.is_consultation:
                    item_price = Decimal('0')
                else:
                    item_price = service_item.custom_price or service.price or Decimal('0')
                
                visit_service = VisitService(
                    visit_id=visit.id,
                    service_id=service.id,
                    code=service.code,
                    name=service.name,
                    qty=service_item.quantity,
                    price=item_price,
                    currency="UZS"
                )
                db.add(visit_service)
            
            created_visits.append(visit)
            total_invoice_amount += visit_amount
            print(f"   ✅ Визит {visit.id} создан успешно для пациента {cart_data.patient_id}")
        
        # Создаём единый invoice
        print(f"📋 REGISTRATION DEBUG: Создаём инвойс на сумму {total_invoice_amount}")
        invoice = PaymentInvoice(
            patient_id=cart_data.patient_id,
            total_amount=total_invoice_amount,
            currency="UZS",
            status="pending",
            payment_method=cart_data.payment_method,
            notes=cart_data.notes
        )
        db.add(invoice)
        db.flush()  # Получаем ID invoice
        print(f"📋 REGISTRATION DEBUG: Инвойс {invoice.id} создан")
        
        # Связываем визиты с invoice
        for visit in created_visits:
            visit_amount = _calculate_visit_price(
                db, 
                [ServiceItemRequest(service_id=vs.service_id, quantity=vs.qty) 
                 for vs in db.query(VisitService).filter(VisitService.visit_id == visit.id).all()],
                cart_data.discount_mode,
                cart_data.patient_id,
                visit.doctor_id
            )
            
            invoice_visit = PaymentInvoiceVisit(
                invoice_id=invoice.id,
                visit_id=visit.id,
                visit_amount=visit_amount
            )
            db.add(invoice_visit)
        
        # Создаём записи в очереди для подтвержденных визитов на сегодня
        # В новом режиме визиты создаются сразу подтвержденными (регистратор)
        queue_numbers = {}
        today = date.today()
        
        for visit in created_visits:
            if visit.visit_date == today and visit.status == "confirmed":
                try:
                    # Используем функцию из утренней сборки для присвоения номеров
                    from app.services.morning_assignment import MorningAssignmentService
                    service = MorningAssignmentService()
                    service.db = db  # Используем существующую сессию
                    queue_assignments = service._assign_queues_for_visit(visit, today)
                    if queue_assignments:
                        visit.status = "open"  # Готов к приему
                        queue_numbers[visit.id] = queue_assignments
                        print(f"✅ REGISTRATION DEBUG: Визит {visit.id} - присвоено {len(queue_assignments)} номеров в очередях")
                    else:
                        print(f"⚠️ REGISTRATION DEBUG: Визит {visit.id} - не удалось присвоить номера в очередях")
                except Exception as e:
                    print(f"⚠️ REGISTRATION DEBUG: Ошибка присвоения очередей для визита {visit.id}: {str(e)}")
                    import traceback
                    print(f"⚠️ TRACEBACK: {traceback.format_exc()}")
                    # Не прерываем создание визита из-за ошибки очередей
                    continue
        
        db.commit()
        print(f"✅ REGISTRATION DEBUG: Транзакция зафиксирована в базе данных!")
        
        # Формируем талоны для визитов с присвоенными номерами очередей
        print_tickets = []
        # Блок формирования талонов пропускаем, так как queue_numbers пустой
        
        # Формируем информацию о созданных визитах
        created_visits_info = []
        try:
            for visit in created_visits:
                # Получаем данные пациента
                patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                patient_name = patient.short_name() if patient else "Неизвестный пациент"
                
                # Получаем данные врача  
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first() if visit.doctor_id else None
                doctor_name = doctor.user.full_name if doctor and doctor.user else "Без врача"
                
                # Получаем услуги визита
                visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
                services_info = []
                for vs in visit_services:
                    services_info.append({
                        "name": vs.name,
                        "code": vs.code,
                        "quantity": vs.qty,
                        "price": float(vs.price) if vs.price else 0
                    })
                
                created_visits_info.append({
                    "visit_id": visit.id,
                    "patient_name": patient_name,
                    "doctor_name": doctor_name,
                    "visit_date": visit.visit_date.isoformat(),
                    "visit_time": visit.visit_time,
                    "status": visit.status,
                    "department": visit.department,
                    "services": services_info,
                    "confirmation_required": visit.status == "pending_confirmation",
                    "confirmation_token": visit.confirmation_token if visit.status == "pending_confirmation" else None
                })
        except Exception as e:
            print(f"⚠️ REGISTRATION DEBUG: Ошибка формирования ответа (визиты уже сохранены): {str(e)}")
            # Визиты уже сохранены, поэтому не откатываем транзакцию
        
        # Определяем сообщение в зависимости от результата
        if queue_numbers:
            message = f"Корзина создана успешно. Присвоено номеров в очередях: {sum(len(assignments) for assignments in queue_numbers.values())}"
        else:
            message = "Визиты созданы. Номера в очередях будут присвоены в день визита."
        
        print(f"✅ REGISTRATION DEBUG: Корзина создана успешно!")
        print(f"   Создано визитов: {len(created_visits)}")
        print(f"   ID визитов: {[v.id for v in created_visits]}")
        print(f"   Invoice ID: {invoice.id}")
        print(f"   Total amount: {total_invoice_amount}")

        return CartResponse(
            success=True,
            message=message,
            invoice_id=invoice.id,
            visit_ids=[v.id for v in created_visits],
            total_amount=total_invoice_amount,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
            created_visits=created_visits_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ REGISTRATION DEBUG: Ошибка создания корзины: {str(e)}")
        import traceback
        print(f"❌ Трейсбек: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания корзины: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ ИЗМЕНЕНИЯМИ ЦЕН =====================

class PriceOverrideApprovalRequest(BaseModel):
    override_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: Optional[str] = None


class PriceOverrideListResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    service_name: str
    doctor_name: str
    doctor_specialty: str
    patient_name: Optional[str]
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: Optional[str]
    status: str
    created_at: datetime


@router.get("/registrar/price-overrides", summary="Получить все изменения цен для одобрения")
def get_pending_price_overrides(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    status_filter: Optional[str] = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=50, ge=1, le=100),
) -> List[PriceOverrideListResponse]:
    """
    Получить список изменений цен для одобрения регистратурой
    """
    try:
        query = db.query(DoctorPriceOverride).join(Service).join(Doctor)
        
        if status_filter != "all":
            query = query.filter(DoctorPriceOverride.status == status_filter)
        
        overrides = query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()
        
        result = []
        for override in overrides:
            # Получаем данные визита и пациента
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            patient_name = None
            if visit:
                # Здесь нужно получить имя пациента из модели Patient
                # Пока используем заглушку
                patient_name = f"Пациент #{visit.patient_id}"
            
            result.append(PriceOverrideListResponse(
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
                created_at=override.created_at
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения изменений цен: {str(e)}"
        )


@router.post("/registrar/price-override/approve", summary="Одобрить или отклонить изменение цены")
def approve_price_override(
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
) -> Dict[str, Any]:
    """
    Одобрить или отклонить изменение цены врачом
    """
    try:
        # Получаем изменение цены
        override = db.query(DoctorPriceOverride).filter(
            DoctorPriceOverride.id == approval_data.override_id
        ).first()
        
        if not override:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Изменение цены не найдено"
            )
        
        if override.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изменение цены уже обработано (статус: {override.status})"
            )
        
        # Обновляем статус
        if approval_data.action == "approve":
            override.status = "approved"
            override.approved_by = current_user.id
            override.approved_at = datetime.utcnow()
            
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
                    "approved_at": override.approved_at.isoformat()
                }
            
            message = "Изменение цены одобрено"
            
        elif approval_data.action == "reject":
            override.status = "rejected"
            override.approved_by = current_user.id
            override.approved_at = datetime.utcnow()
            override.rejection_reason = approval_data.rejection_reason
            
            message = "Изменение цены отклонено"
        
        db.commit()
        db.refresh(override)
        
        return {
            "success": True,
            "message": message,
            "override_id": override.id,
            "new_status": override.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки изменения цены: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ ЛЬГОТАМИ ALL FREE =====================

class AllFreeApprovalRequest(BaseModel):
    visit_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: Optional[str] = None


class AllFreeVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str]
    patient_phone: Optional[str]
    services: List[str]
    total_original_amount: Decimal
    doctor_name: Optional[str]
    doctor_specialty: Optional[str]
    visit_date: Optional[date]
    visit_time: Optional[str]
    notes: Optional[str]
    created_at: datetime
    approval_status: str


@router.get("/admin/all-free-requests", summary="Получить заявки All Free для одобрения")
def get_all_free_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    status_filter: Optional[str] = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=50, ge=1, le=100),
) -> List[AllFreeVisitResponse]:
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
            # Получаем услуги визита
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
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
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                if doctor:
                    doctor_name = f"Врач #{doctor.id}"  # Здесь нужно получить имя врача
                    doctor_specialty = doctor.specialty
            
            # Получаем данные пациента (заглушка)
            patient_name = f"Пациент #{visit.patient_id}"
            patient_phone = None  # Здесь нужно получить телефон пациента
            
            result.append(AllFreeVisitResponse(
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
                approval_status=visit.approval_status
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения заявок All Free: {str(e)}"
        )


@router.post("/admin/all-free-approve", summary="Одобрить или отклонить заявку All Free")
def approve_all_free_request(
    approval_data: AllFreeApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
) -> Dict[str, Any]:
    """
    Одобрить или отклонить заявку All Free администратором
    """
    try:
        # Получаем визит
        visit = db.query(Visit).filter(Visit.id == approval_data.visit_id).first()
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        if visit.discount_mode != "all_free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это не заявка All Free"
            )
        
        if visit.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заявка уже обработана (статус: {visit.approval_status})"
            )
        
        # Обновляем статус
        if approval_data.action == "approve":
            visit.approval_status = "approved"
            message = "Заявка All Free одобрена"
            
        elif approval_data.action == "reject":
            visit.approval_status = "rejected"
            # Можно добавить поле для причины отклонения в модель Visit
            if approval_data.rejection_reason:
                visit.notes = (visit.notes or "") + f"\nОтклонено: {approval_data.rejection_reason}"
            
            message = "Заявка All Free отклонена"
        
        db.commit()
        db.refresh(visit)
        
        return {
            "success": True,
            "message": message,
            "visit_id": visit.id,
            "new_status": visit.approval_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки заявки All Free: {str(e)}"
        )


# ===================== НАСТРОЙКИ ЛЬГОТ =====================

class BenefitSettingsRequest(BaseModel):
    repeat_visit_days: int = Field(default=21, ge=1, le=365)  # Окно повторного визита в днях
    repeat_visit_discount: int = Field(default=0, ge=0, le=100)  # Скидка на повторный визит в %
    benefit_consultation_free: bool = Field(default=True)  # Льготные консультации бесплатны
    all_free_auto_approve: bool = Field(default=False)  # Автоодобрение All Free заявок


class BenefitSettingsResponse(BaseModel):
    repeat_visit_days: int
    repeat_visit_discount: int
    benefit_consultation_free: bool
    all_free_auto_approve: bool
    updated_at: datetime


@router.get("/admin/benefit-settings", summary="Получить настройки льгот")
def get_benefit_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
) -> BenefitSettingsResponse:
    """
    Получить текущие настройки льгот и повторных визитов
    """
    try:
        # Получаем настройки из базы данных
        settings = {}
        
        # Окно повторного визита (дни)
        repeat_days_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "repeat_visit_days"
        ).first()
        settings['repeat_visit_days'] = int(repeat_days_setting.value) if repeat_days_setting else 21
        
        # Скидка на повторный визит (%)
        repeat_discount_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "repeat_visit_discount"
        ).first()
        settings['repeat_visit_discount'] = int(repeat_discount_setting.value) if repeat_discount_setting else 0
        
        # Льготные консультации бесплатны
        benefit_free_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "benefit_consultation_free"
        ).first()
        settings['benefit_consultation_free'] = bool(benefit_free_setting.value) if benefit_free_setting else True
        
        # Автоодобрение All Free заявок
        auto_approve_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "all_free_auto_approve"
        ).first()
        settings['all_free_auto_approve'] = bool(auto_approve_setting.value) if auto_approve_setting else False
        
        # Время последнего обновления
        latest_update = db.query(ClinicSettings).filter(
            ClinicSettings.key.in_([
                "repeat_visit_days", "repeat_visit_discount", 
                "benefit_consultation_free", "all_free_auto_approve"
            ])
        ).order_by(ClinicSettings.updated_at.desc()).first()
        
        updated_at = latest_update.updated_at if latest_update else datetime.utcnow()
        
        return BenefitSettingsResponse(
            repeat_visit_days=settings['repeat_visit_days'],
            repeat_visit_discount=settings['repeat_visit_discount'],
            benefit_consultation_free=settings['benefit_consultation_free'],
            all_free_auto_approve=settings['all_free_auto_approve'],
            updated_at=updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек льгот: {str(e)}"
        )


@router.post("/admin/benefit-settings", summary="Обновить настройки льгот")
def update_benefit_settings(
    settings_data: BenefitSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
) -> Dict[str, Any]:
    """
    Обновить настройки льгот и повторных визитов
    """
    try:
        # Список настроек для обновления
        settings_to_update = [
            {
                "key": "repeat_visit_days",
                "value": settings_data.repeat_visit_days,
                "description": "Окно повторного визита в днях"
            },
            {
                "key": "repeat_visit_discount",
                "value": settings_data.repeat_visit_discount,
                "description": "Скидка на повторный визит в процентах"
            },
            {
                "key": "benefit_consultation_free",
                "value": settings_data.benefit_consultation_free,
                "description": "Льготные консультации бесплатны"
            },
            {
                "key": "all_free_auto_approve",
                "value": settings_data.all_free_auto_approve,
                "description": "Автоматическое одобрение All Free заявок"
            }
        ]
        
        # Обновляем каждую настройку
        for setting_data in settings_to_update:
            setting = db.query(ClinicSettings).filter(
                ClinicSettings.key == setting_data["key"]
            ).first()
            
            if setting:
                # Обновляем существующую настройку
                setting.value = setting_data["value"]
                setting.updated_by = current_user.id
                setting.updated_at = datetime.utcnow()
            else:
                # Создаём новую настройку
                setting = ClinicSettings(
                    key=setting_data["key"],
                    value=setting_data["value"],
                    category="benefits",
                    description=setting_data["description"],
                    updated_by=current_user.id
                )
                db.add(setting)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Настройки льгот обновлены успешно",
            "settings": {
                "repeat_visit_days": settings_data.repeat_visit_days,
                "repeat_visit_discount": settings_data.repeat_visit_discount,
                "benefit_consultation_free": settings_data.benefit_consultation_free,
                "all_free_auto_approve": settings_data.all_free_auto_approve
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек льгот: {str(e)}"
        )


# ==================== НАСТРОЙКИ МАСТЕРА РЕГИСТРАЦИИ ====================

class WizardSettingsResponse(BaseModel):
    use_new_wizard: bool
    updated_at: datetime

class WizardSettingsRequest(BaseModel):
    use_new_wizard: bool = Field(default=False, description="Использовать новый мастер регистрации")

@router.get("/admin/wizard-settings", summary="Получить настройки мастера регистрации")
def get_wizard_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """Получить настройки мастера регистрации"""
    try:
        # Получаем настройку использования нового мастера
        use_new_wizard_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "wizard_use_new_version"
        ).first()
        
        use_new_wizard = False
        updated_at = datetime.utcnow()
        
        if use_new_wizard_setting:
            use_new_wizard = use_new_wizard_setting.value.get("enabled", False) if use_new_wizard_setting.value else False
            updated_at = use_new_wizard_setting.updated_at or updated_at
        
        return WizardSettingsResponse(
            use_new_wizard=use_new_wizard,
            updated_at=updated_at
        )
        
    except Exception as e:
        logger.error(f"Error getting wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении настроек мастера"
        )

@router.post("/admin/wizard-settings", summary="Обновить настройки мастера регистрации")
def update_wizard_settings(
    settings_data: WizardSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки мастера регистрации"""
    try:
        # Обновляем или создаем настройку
        use_new_wizard_setting = db.query(ClinicSettings).filter(
            ClinicSettings.key == "wizard_use_new_version"
        ).first()
        
        if not use_new_wizard_setting:
            use_new_wizard_setting = ClinicSettings(
                key="wizard_use_new_version",
                category="wizard",
                description="Использовать новый мастер регистрации вместо старого"
            )
            db.add(use_new_wizard_setting)
        
        use_new_wizard_setting.value = {
            "enabled": settings_data.use_new_wizard,
            "updated_by": current_user.id
        }
        use_new_wizard_setting.updated_by = current_user.id
        use_new_wizard_setting.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(use_new_wizard_setting)
        
        settings_response = WizardSettingsResponse(
            use_new_wizard=settings_data.use_new_wizard,
            updated_at=use_new_wizard_setting.updated_at
        )
        
        return {
            "success": True,
            "message": f"Настройки мастера обновлены. {'Включен новый мастер' if settings_data.use_new_wizard else 'Включен старый мастер'}",
            "settings": settings_response
        }
        
    except Exception as e:
        logger.error(f"Error updating wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении настроек мастера"
        )


# ===================== ЭНДПОИНТ ДЛЯ ПОЛУЧЕНИЯ ЗАПИСЕЙ ИЗ VISITS =====================

class VisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_fio: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    department: Optional[str] = None
    visit_date: Optional[date] = None
    visit_time: Optional[str] = None
    status: str
    discount_mode: str
    approval_status: str
    services: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: datetime

@router.get("/registrar/visits", response_model=List[VisitResponse])
def get_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None, description="Фильтр по ID пациента"),
    doctor_id: Optional[int] = Query(None, description="Фильтр по ID врача"),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
):
    """Получить объединенный список записей из таблиц visits (новый мастер) и appointments (старый мастер)"""
    try:
        from app.models.visit import Visit, VisitService
        from app.models.service import Service
        from app.models.clinic import Doctor
        from app.models.patient import Patient
        from app.models.appointment import Appointment
        
        result = []
        
        # 1. ПОЛУЧАЕМ ЗАПИСИ ИЗ СТАРОЙ ТАБЛИЦЫ APPOINTMENTS СНАЧАЛА
        try:
            appointments = db.query(Appointment).order_by(Appointment.created_at.desc()).limit(5).all()
            
            # Обрабатываем записи из appointments
            for appointment in appointments:
                # Получаем данные пациента
                patient_fio = f"Пациент #{appointment.patient_id}"
                patient_phone = None
                try:
                    if appointment.patient_id:
                        patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
                        if patient:
                            patient_fio = patient.short_name()
                            patient_phone = patient.phone
                except Exception:
                    pass
                
                result.append(VisitResponse(
                    id=appointment.id + 10000,  # Добавляем смещение чтобы избежать конфликтов ID
                    patient_id=appointment.patient_id,
                    patient_fio=patient_fio,
                    patient_phone=patient_phone,
                    doctor_id=appointment.doctor_id,
                    doctor_name=None,
                    doctor_specialty=None,
                    department=appointment.department,
                    visit_date=appointment.appointment_date,
                    visit_time=appointment.appointment_time,
                    status=appointment.status,
                    discount_mode="none",
                    approval_status="approved",
                    services=appointment.services or [],
                    notes=appointment.notes,
                    created_at=appointment.created_at
                ))
        except Exception as e:
            print(f"DEBUG: Error processing appointments: {e}")
        
        # 2. ПОЛУЧАЕМ ЗАПИСИ ИЗ НОВОЙ ТАБЛИЦЫ VISITS
        visits_query = db.query(Visit)
        
        # Фильтры для visits
        if patient_id:
            visits_query = visits_query.filter(Visit.patient_id == patient_id)
        if doctor_id:
            visits_query = visits_query.filter(Visit.doctor_id == doctor_id)
        if department:
            visits_query = visits_query.filter(Visit.department == department)
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass
        
        visits = visits_query.order_by(Visit.created_at.desc()).all()
        
        # Обрабатываем записи из visits
        for visit in visits:
            # Получаем услуги визита
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            service_names = []
            for vs in visit_services:
                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                else:  # Fallback - ищем в таблице services
                    service = db.query(Service).filter(Service.id == vs.service_id).first()
                    if service:
                        service_names.append(service.name)
            
            # Получаем данные врача
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                if doctor and doctor.user:
                    doctor_name = doctor.user.full_name
                    doctor_specialty = doctor.specialty
                elif doctor:
                    doctor_name = f"Врач #{doctor.id}"
                    doctor_specialty = doctor.specialty
            
            # Получаем данные пациента
            patient_fio = f"Пациент #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                if patient:
                    patient_fio = patient.short_name()
                    patient_phone = patient.phone
            
            result.append(VisitResponse(
                id=visit.id,
                patient_id=visit.patient_id,
                patient_fio=patient_fio,
                patient_phone=patient_phone,
                doctor_id=visit.doctor_id,
                doctor_name=doctor_name,
                doctor_specialty=doctor_specialty,
                department=visit.department,
                visit_date=visit.visit_date,
                visit_time=visit.visit_time,
                status=visit.status,
                discount_mode=visit.discount_mode,
                approval_status=visit.approval_status,
                services=service_names,
                notes=visit.notes,
                created_at=visit.created_at
            ))
        
        
        # Сортируем объединенный результат по дате создания
        result.sort(key=lambda x: x.created_at, reverse=True)
        
        # Применяем пагинацию к объединенному результату
        total_results = result[skip:skip + limit]
        
        return total_results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения записей: {str(e)}"
        )


# ===================== ПРОСТОЙ ЭНДПОИНТ ДЛЯ ОБЪЕДИНЕНИЯ ДАННЫХ =====================



@router.get("/registrar/all-appointments")
def get_all_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Поиск по ФИО, телефону или услугам")
):
    """Простое объединение appointments + visits для фронтенда"""
    try:
        from app.models.appointment import Appointment
        from app.models.visit import Visit
        from app.models.patient import Patient
        from sqlalchemy import or_, func
        
        result = []
        
        # 1. Получаем старые appointments с фильтрацией
        appointments_query = db.query(Appointment)
        
        # Применяем фильтры по дате
        if date_from:
            appointments_query = appointments_query.filter(Appointment.appointment_date >= date_from)
        if date_to:
            appointments_query = appointments_query.filter(Appointment.appointment_date <= date_to)
        
        # Применяем поиск
        if search:
            # Для поиска по телефону извлекаем только цифры
            search_digits = ''.join(filter(str.isdigit, search))
            
            if search_digits:
                # Поиск по ФИО, телефону и ID записи (включая только цифры)
                appointments_query = appointments_query.join(Patient, Appointment.patient_id == Patient.id).filter(
                    or_(
                        Patient.full_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(f"%{search_digits}%"),
                        Appointment.id.cast(String).ilike(f"%{search_digits}%")
                    )
                )
            else:
                # Если нет цифр, ищем только по ФИО
                appointments_query = appointments_query.join(Patient, Appointment.patient_id == Patient.id).filter(
                    Patient.full_name.ilike(f"%{search}%")
                )
        
        appointments = appointments_query.order_by(Appointment.created_at.desc()).limit(limit//2).all()
        for apt in appointments:
            # Получаем имя пациента
            patient_fio = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_fio = patient.short_name()
            
            # Преобразуем ID услуг в названия для appointments
            service_names = []
            service_codes = []
            total_amount = 0
            
            if apt.services and isinstance(apt.services, list):
                from app.models.service import Service
                for service_id in apt.services:
                    try:
                        service_id_int = int(service_id)
                        service = db.query(Service).filter(Service.id == service_id_int).first()
                        if service:
                            service_names.append(service.name)
                            if service.code:
                                service_codes.append(service.code)
                            if service.price:
                                total_amount += float(service.price)
                    except (ValueError, TypeError):
                        # Если service_id не число, возможно это уже название
                        service_names.append(str(service_id))
            
            # Определяем payment_status для Appointment
            payment_status = 'pending'
            is_paid = False
            visit_type = getattr(apt, 'visit_type', None)
            if visit_type == 'paid':
                payment_status = 'paid'
                is_paid = True
            elif apt.status and apt.status.lower() in ('paid', 'in_visit', 'completed', 'done'):
                payment_status = 'paid'
                is_paid = True
            elif getattr(apt, 'payment_processed_at', None):
                payment_status = 'paid'
                is_paid = True
            else:
                # Проверяем Payment table
                try:
                    from app.models.payment import Payment
                    from sqlalchemy import and_
                    # Ищем связанный Visit
                    related_visit = db.query(Visit).filter(
                        and_(
                            Visit.patient_id == apt.patient_id,
                            Visit.visit_date == apt.appointment_date,
                            Visit.doctor_id == apt.doctor_id
                        )
                    ).first()
                    if related_visit:
                        payment_row = db.query(Payment).filter(Payment.visit_id == related_visit.id).order_by(Payment.created_at.desc()).first()
                        if payment_row and (str(payment_row.status).lower() == 'paid' or payment_row.paid_at):
                            payment_status = 'paid'
                            is_paid = True
                except Exception:
                    pass

            # ✅ ВАЖНО: Сохраняем visit_type в БД для существующих записей
            if is_paid and apt.visit_type != 'paid':
                apt.visit_type = 'paid'
                try:
                    db.commit()
                    db.refresh(apt)
                except Exception:
                    db.rollback()

            result.append({
                'id': apt.id,
                'patient_id': apt.patient_id,
                'patient_fio': patient_fio,
                'doctor_id': apt.doctor_id,
                'department': apt.department,
                'appointment_date': apt.appointment_date,
                'appointment_time': apt.appointment_time,
                'status': apt.status,
                'services': service_names,  # Преобразованные названия услуг
                'service_codes': service_codes,  # Коды услуг для фильтрации
                'total_amount': total_amount,  # Общая сумма услуг
                'payment_status': payment_status,  # ✅ ДОБАВЛЕНО: Статус оплаты
                'visit_type': visit_type,  # Тип визита для совместимости
                'notes': apt.notes,
                'created_at': apt.created_at,
                'source': 'appointments',
                'queue_numbers': [],  # Старые appointments не имеют номеров в новых очередях
                'confirmation_status': 'none',  # Старые appointments не требуют подтверждения
                'confirmed_at': None,
                'confirmed_by': None
            })
        
        # 2. Получаем новые visits с фильтрацией
        visits_query = db.query(Visit)
        
        # Применяем фильтры по дате
        if date_from:
            visits_query = visits_query.filter(Visit.visit_date >= date_from)
        if date_to:
            visits_query = visits_query.filter(Visit.visit_date <= date_to)
        
        # Применяем поиск
        if search:
            # Для поиска по телефону извлекаем только цифры
            search_digits = ''.join(filter(str.isdigit, search))
            
            if search_digits:
                # Поиск по ФИО, телефону и ID записи (включая только цифры)
                visits_query = visits_query.join(Patient, Visit.patient_id == Patient.id).filter(
                    or_(
                        Patient.full_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(f"%{search_digits}%"),
                        Visit.id.cast(String).ilike(f"%{search_digits}%")
                    )
                )
            else:
                # Если нет цифр, ищем только по ФИО
                visits_query = visits_query.join(Patient, Visit.patient_id == Patient.id).filter(
                    Patient.full_name.ilike(f"%{search}%")
                )
        
        visits = visits_query.order_by(Visit.created_at.desc()).limit(limit//2).all()
        for visit in visits:
            # Получаем имя пациента
            patient_fio = None
            if visit.patient_id:
                patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                if patient:
                    patient_fio = patient.short_name()
            
            # Получаем услуги визита
            from app.models.visit import VisitService
            from app.models.service import Service
            
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            service_names = []
            service_codes = []
            total_amount = 0
            
            for vs in visit_services:
                service_price = 0
                if vs.price is not None:  # Используем сохраненную цену (включая 0)
                    service_price = float(vs.price)
                elif vs.service_id:  # Fallback - ищем цену в таблице services
                    service = db.query(Service).filter(Service.id == vs.service_id).first()
                    if service and service.price:
                        service_price = float(service.price)
                
                total_amount += service_price * (vs.qty or 1)
                
                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                    if vs.code:
                        service_codes.append(vs.code)
                else:  # Fallback - ищем в таблице services
                    service = db.query(Service).filter(Service.id == vs.service_id).first()
                    if service:
                        service_names.append(service.name)
                        if service.code:
                            service_codes.append(service.code)
            
            # Получаем информацию о номерах в очередях для визита
            queue_numbers = []
            confirmation_status = None
            
            if visit.visit_date == date.today():
                # Ищем записи в очередях для этого визита
                from app.models.online_queue import OnlineQueueEntry, DailyQueue
                queue_entries = db.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.visit_id == visit.id
                ).all()
                
                for entry in queue_entries:
                    queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                    if queue:
                        queue_names = {
                            "ecg": "ЭКГ",
                            "cardiology_common": "Кардиолог",
                            "dermatology": "Дерматолог", 
                            "stomatology": "Стоматолог",
                            "cosmetology": "Косметолог",
                            "lab": "Лаборатория",
                            "general": "Общая очередь"
                        }
                        
                        queue_numbers.append({
                            "queue_tag": queue.queue_tag or "general",
                            "queue_name": queue_names.get(queue.queue_tag or "general", queue.queue_tag or "Общая"),
                            "number": entry.number,
                            "status": entry.status
                        })
            
            # Определяем статус подтверждения
            if visit.status == "pending_confirmation":
                confirmation_status = "pending"
            elif visit.confirmed_at:
                confirmation_status = "confirmed"
            else:
                confirmation_status = "none"

            # Определяем payment_status для Visit (та же логика что в registrar_integration.py)
            payment_status = 'pending'
            is_paid = False
            try:
                v_status = (getattr(visit, 'status', None) or '').lower()
                if v_status in ("paid", "in_visit", "in progress", "completed", "done"):
                    payment_status = 'paid'
                    is_paid = True
                elif getattr(visit, 'payment_processed_at', None):
                    payment_status = 'paid'
                    is_paid = True
                else:
                    # Проверяем Payment table
                    from app.models.payment import Payment
                    payment_row = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                    if payment_row and (str(payment_row.status).lower() == 'paid' or payment_row.paid_at):
                        payment_status = 'paid'
                        is_paid = True
                    elif visit.discount_mode == 'paid' and v_status in ("paid", "in_visit", "in progress", "completed", "done"):
                        payment_status = 'paid'
                        is_paid = True
                    elif visit.discount_mode == 'paid' and getattr(visit, 'payment_processed_at', None):
                        payment_status = 'paid'
                        is_paid = True
            except Exception:
                # Если не удалось определить, проверяем discount_mode
                if visit.discount_mode == 'paid':
                    payment_status = 'paid'
                    is_paid = True

            # ✅ ВАЖНО: Сохраняем discount_mode в БД для существующих записей
            if is_paid and visit.discount_mode != 'paid':
                visit.discount_mode = 'paid'
                try:
                    db.commit()
                    db.refresh(visit)
                except Exception:
                    db.rollback()

            result.append({
                'id': visit.id + 20000,  # Смещение для избежания конфликтов
                'patient_id': visit.patient_id,
                'patient_fio': patient_fio,
                'doctor_id': visit.doctor_id,
                'department': visit.department,
                'appointment_date': visit.visit_date,
                'appointment_time': visit.visit_time,
                'status': visit.status,
                'services': service_names,  # Реальные названия услуг
                'service_codes': service_codes,  # Коды услуг для фильтрации
                'total_amount': total_amount,  # Общая сумма услуг
                'payment_status': payment_status,  # ✅ ДОБАВЛЕНО: Статус оплаты
                'discount_mode': visit.discount_mode,  # Тип визита для отображения
                'notes': visit.notes,
                'created_at': visit.created_at,
                'source': 'visits',
                'queue_numbers': queue_numbers,  # Номера в очередях
                'confirmation_status': confirmation_status,  # Статус подтверждения
                'confirmed_at': visit.confirmed_at.isoformat() if visit.confirmed_at else None,
                'confirmed_by': visit.confirmed_by
            })
        
        # Сортируем по дате создания
        result.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Применяем пагинацию
        paginated_result = result[offset:offset + limit]
        
        return {
            "data": paginated_result,
            "total": len(result),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения записей: {str(e)}"
        )


# ===================== ЭНДПОИНТ ДЛЯ ОТМЕТКИ ЗАПИСЕЙ ИЗ VISITS КАК ОПЛАЧЕННЫХ =====================

@router.post("/registrar/visits/{visit_id}/mark-paid")
def mark_visit_as_paid(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor"))
):
    """Отметить запись из таблицы visits как оплаченную"""
    try:
        from app.models.visit import Visit
        
        # Логирование для диагностики
        print(f"[mark_visit_as_paid] User: {current_user.username}, Role: {current_user.role}, Visit ID: {visit_id}")
        
        # Находим запись
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
            )
        
        # Обновляем статус и discount_mode
        visit.status = "paid"
        visit.discount_mode = "paid"  # ✅ ВАЖНО: устанавливаем discount_mode для корректного отображения payment_status
        db.commit()
        db.refresh(visit)
        
        return {
            "id": visit.id,
            "status": visit.status,
            "message": "Запись отмечена как оплаченная"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[mark_visit_as_paid] Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления записи: {str(e)}"
        )


@router.post("/registrar/visits/{visit_id}/complete")
def complete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor"))
):
    """Завершить запись из таблицы visits"""
    try:
        from app.models.visit import Visit
        
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
            )
        
        visit.status = "completed"
        db.commit()
        db.refresh(visit)
        
        return {
            "id": visit.id,
            "status": visit.status,
            "message": "Запись завершена"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления записи: {str(e)}"
        )


@router.post("/registrar/visits/{visit_id}/start-visit")
def start_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """Начать прием (в кабинете) для записи из таблицы visits"""
    try:
        from app.models.visit import Visit
        
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
            )
        
        visit.status = "in_progress"
        db.commit()
        db.refresh(visit)
        
        return {
            "id": visit.id,
            "status": visit.status,
            "message": "Прием начат"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления записи: {str(e)}"
        )
"""
Эндпоинты подтверждения визитов
Временный файл для добавления в registrar_wizard.py
"""

# ===================== ПОДТВЕРЖДЕНИЕ ВИЗИТОВ =====================

class ConfirmVisitRequest(BaseModel):
    confirmation_method: str = Field(default="phone", pattern="^(phone|manual)$")
    confirmed_by: Optional[str] = None  # Номер телефона или ID сотрудника
    notes: Optional[str] = None

class ConfirmVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    queue_numbers: Optional[Dict[str, Any]] = None
    print_tickets: Optional[List[Dict[str, Any]]] = None

@router.post("/registrar/visits/{visit_id}/confirm", response_model=ConfirmVisitResponse)
def confirm_visit_by_registrar(
    visit_id: int,
    request: ConfirmVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Подтверждение визита регистратором (по телефону)
    Присваивает номера в очередях если визит на сегодня
    """
    try:
        # Находим визит
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Проверяем что визит ожидает подтверждения
        if visit.status != "pending_confirmation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Визит уже имеет статус: {visit.status}"
            )
        
        # Проверяем что токен не истек
        if visit.confirmation_expires_at and visit.confirmation_expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок подтверждения истек"
            )
        
        # Подтверждаем визит
        visit.confirmed_at = datetime.utcnow()
        visit.confirmed_by = request.confirmed_by or f"registrar_{current_user.id}"
        visit.status = "confirmed"
        
        queue_numbers = {}
        print_tickets = []
        
        # Если визит на сегодня - присваиваем номера в очередях
        if visit.visit_date == date.today():
            queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(db, visit)
            visit.status = "open"  # Готов к приему
        
        db.commit()
        db.refresh(visit)
        
        return ConfirmVisitResponse(
            success=True,
            message=f"Визит подтвержден. {'Номера в очередях присвоены.' if queue_numbers else 'Номера будут присвоены утром в день визита.'}",
            visit_id=visit.id,
            status=visit.status,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подтверждения визита: {str(e)}"
        )


def _assign_queue_numbers_on_confirmation(db: Session, visit: Visit) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Присваивает номера в очередях при подтверждении визита на сегодня
    Возвращает (queue_numbers, print_tickets)
    """
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    
    # Получаем услуги визита
    visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
    
    # Определяем уникальные queue_tag из услуг
    unique_queue_tags = set()
    for vs in visit_services:
        service = db.query(Service).filter(Service.id == vs.service_id).first()
        if service and service.queue_tag:
            unique_queue_tags.add(service.queue_tag)
    
    if not unique_queue_tags:
        return {}, []
    
    today = date.today()
    queue_numbers = {}
    print_tickets = []
    
    # Получаем настройки очередей
    queue_settings = {}  # Можно загрузить из настроек
    
    for queue_tag in unique_queue_tags:
        # Определяем врача для очереди
        doctor_id = visit.doctor_id
        
        # Для очередей без конкретного врача используем ресурс-врачей
        if queue_tag == "ecg" and not doctor_id:
            ecg_resource = db.query(User).filter(
                User.username == "ecg_resource",
                User.is_active == True
            ).first()
            if ecg_resource:
                doctor_id = ecg_resource.id
            else:
                continue
                
        elif queue_tag == "lab" and not doctor_id:
            lab_resource = db.query(User).filter(
                User.username == "lab_resource",
                User.is_active == True
            ).first()
            if lab_resource:
                doctor_id = lab_resource.id
            else:
                continue
        
        if not doctor_id:
            continue
        
        # Получаем или создаем дневную очередь
        daily_queue = crud_queue.get_or_create_daily_queue(db, today, doctor_id, queue_tag)
        
        # Подсчитываем текущее количество записей в очереди
        current_count = crud_queue.count_queue_entries(db, daily_queue.id)
        start_number = queue_settings.get("start_numbers", {}).get(queue_tag, 1)
        next_number = start_number + current_count
        
        # Создаем запись в очереди
        queue_entry = OnlineQueueEntry(
            queue_id=daily_queue.id,
            patient_id=visit.patient_id,
            number=next_number,
            status="waiting",
            source="confirmation"  # Источник: подтверждение визита
        )
        db.add(queue_entry)
        
        queue_numbers[queue_tag] = {
            "queue_tag": queue_tag,
            "number": next_number,
            "queue_id": daily_queue.id
        }
        
        # Подготавливаем данные для печати талона
        queue_names = {
            "ecg": "ЭКГ",
            "cardiology_common": "Кардиолог",
            "dermatology": "Дерматолог", 
            "stomatology": "Стоматолог",
            "cosmetology": "Косметолог",
            "lab": "Лаборатория",
            "general": "Общая очередь"
        }
        
        doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first() if visit.doctor_id else None
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        
        print_tickets.append({
            "visit_id": visit.id,
            "queue_tag": queue_tag,
            "queue_name": queue_names.get(queue_tag, queue_tag),
            "queue_number": next_number,
            "queue_id": daily_queue.id,
            "patient_id": visit.patient_id,
            "patient_name": patient.short_name() if patient else "Неизвестный пациент",
            "doctor_name": doctor.user.full_name if doctor and doctor.user else "Без врача",
            "department": visit.department,
            "visit_date": visit.visit_date.isoformat(),
            "visit_time": visit.visit_time
        })
    
    return queue_numbers, print_tickets
