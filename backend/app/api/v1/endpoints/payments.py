"""
API endpoints для платежной системы
"""
from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api import deps
from app.core.config import settings
from app.db.session import get_db
from app.models.payment import Payment
from app.models.payment_webhook import PaymentWebhook, PaymentProvider, PaymentTransaction
from app.models.visit import Visit
from app.services.payment_providers.manager import PaymentProviderManager
from app.services.payment_providers.base import PaymentResult, PaymentStatus

router = APIRouter()

# ===================== МОДЕЛИ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================

class PaymentInvoiceCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма к оплате")
    currency: str = Field(default="UZS", description="Валюта")
    provider: str = Field(..., pattern="^(click|payme)$", description="Платежный провайдер")
    description: Optional[str] = Field(None, description="Описание платежа")
    patient_info: Optional[Dict[str, Any]] = Field(None, description="Информация о пациенте")

class PaymentInvoiceResponse(BaseModel):
    invoice_id: int
    amount: Decimal
    currency: str
    provider: str
    status: str
    description: Optional[str]
    created_at: datetime

class PendingInvoicesResponse(BaseModel):
    invoices: List[PaymentInvoiceResponse]

# Инициализация менеджера провайдеров
payment_manager = None

def get_payment_manager() -> PaymentProviderManager:
    """Получение менеджера провайдеров платежей"""
    global payment_manager
    
    if payment_manager is None:
        # Конфигурация провайдеров из настроек
        config = {
            "click": {
                "enabled": getattr(settings, "CLICK_ENABLED", True),  # Включено для тестирования
                "service_id": getattr(settings, "CLICK_SERVICE_ID", "test_service"),
                "merchant_id": getattr(settings, "CLICK_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "CLICK_SECRET_KEY", "test_secret"),
                "base_url": getattr(settings, "CLICK_BASE_URL", "https://api.click.uz/v2")
            },
            "payme": {
                "enabled": getattr(settings, "PAYME_ENABLED", True),  # Включено для тестирования
                "merchant_id": getattr(settings, "PAYME_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "PAYME_SECRET_KEY", "test_secret"),
                "base_url": getattr(settings, "PAYME_BASE_URL", "https://checkout.paycom.uz"),
                "api_url": getattr(settings, "PAYME_API_URL", "https://api.paycom.uz")
            },
            "kaspi": {
                "enabled": getattr(settings, "KASPI_ENABLED", True),  # Включено для тестирования
                "merchant_id": getattr(settings, "KASPI_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "KASPI_SECRET_KEY", "test_secret"),
                "base_url": getattr(settings, "KASPI_BASE_URL", "https://kaspi.kz/pay"),
                "api_url": getattr(settings, "KASPI_API_URL", "https://api.kaspi.kz/pay/v1")
            }
        }
        
        payment_manager = PaymentProviderManager(config)
    
    return payment_manager

# Pydantic модели
class PaymentInitRequest(BaseModel):
    """Запрос на инициализацию платежа"""
    visit_id: int = Field(..., description="ID визита")
    provider: str = Field(..., description="Провайдер платежа (click, payme, kaspi)")
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")
    currency: str = Field(default="UZS", description="Валюта платежа")
    description: Optional[str] = Field(None, description="Описание платежа")
    return_url: Optional[str] = Field(None, description="URL возврата при успехе")
    cancel_url: Optional[str] = Field(None, description="URL возврата при отмене")

class PaymentInitResponse(BaseModel):
    """Ответ на инициализацию платежа"""
    success: bool
    payment_id: Optional[int] = None
    provider_payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None

class PaymentStatusResponse(BaseModel):
    """Ответ на запрос статуса платежа"""
    payment_id: int
    status: str
    amount: Decimal
    currency: str
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    provider_data: Optional[Dict[str, Any]] = None

class PaymentListResponse(BaseModel):
    """Список платежей"""
    payments: List[PaymentStatusResponse]
    total: int

class ProviderInfo(BaseModel):
    """Информация о провайдере"""
    name: str
    code: str
    supported_currencies: List[str]
    is_active: bool
    features: Dict[str, bool]

class ProvidersResponse(BaseModel):
    """Список доступных провайдеров"""
    providers: List[ProviderInfo]

# API Endpoints

@router.get("/providers", response_model=ProvidersResponse)
def get_available_providers(
    db: Session = Depends(get_db)
) -> ProvidersResponse:
    """Получение списка доступных провайдеров платежей"""
    
    manager = get_payment_manager()
    provider_info = manager.get_provider_info()
    
    providers = []
    for code, info in provider_info.items():
        providers.append(ProviderInfo(
            name=info["name"],
            code=code,
            supported_currencies=info["supported_currencies"],
            is_active=True,
            features=info["features"]
        ))
    
    return ProvidersResponse(providers=providers)

@router.post("/init", response_model=PaymentInitResponse)
def init_payment(
    payment_request: PaymentInitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
) -> PaymentInitResponse:
    """Инициализация платежа"""
    
    try:
        # Проверяем существование визита
        visit = db.query(Visit).filter(Visit.id == payment_request.visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Получаем менеджер провайдеров
        manager = get_payment_manager()
        
        # Проверяем поддержку провайдера и валюты
        supported_providers = manager.get_providers_for_currency(payment_request.currency)
        if payment_request.provider not in supported_providers:
            return PaymentInitResponse(
                success=False,
                error_message=f"Провайдер {payment_request.provider} не поддерживает валюту {payment_request.currency}"
            )
        
        # Создаем запись платежа в БД
        payment = Payment(
            visit_id=payment_request.visit_id,
            amount=payment_request.amount,
            currency=payment_request.currency,
            method="online",
            status="pending",
            provider=payment_request.provider
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Генерируем order_id
        order_id = f"clinic_{payment.id}_{int(datetime.now().timestamp())}"
        
        # Формируем URLs
        base_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        return_url = payment_request.return_url or f"{base_url}/payment/success?payment_id={payment.id}"
        cancel_url = payment_request.cancel_url or f"{base_url}/payment/cancel?payment_id={payment.id}"
        
        # Создаем платеж у провайдера
        result = manager.create_payment(
            provider_name=payment_request.provider,
            amount=payment_request.amount,
            currency=payment_request.currency,
            order_id=order_id,
            description=payment_request.description or f"Оплата визита #{visit.id}",
            return_url=return_url,
            cancel_url=cancel_url
        )
        
        if result.success:
            # Обновляем платеж данными от провайдера
            payment.provider_payment_id = result.payment_id
            payment.payment_url = result.payment_url
            payment.status = result.status or "pending"
            payment.provider_data = result.provider_data
            
            db.commit()
            
            return PaymentInitResponse(
                success=True,
                payment_id=payment.id,
                provider_payment_id=result.payment_id,
                payment_url=result.payment_url,
                status=result.status
            )
        else:
            # Обновляем статус на failed
            payment.status = "failed"
            payment.provider_data = {"error": result.error_message}
            db.commit()
            
            return PaymentInitResponse(
                success=False,
                payment_id=payment.id,
                error_message=result.error_message
            )
    
    except HTTPException:
        raise
    except Exception as e:
        return PaymentInitResponse(
            success=False,
            error_message=f"Ошибка инициализации платежа: {str(e)}"
        )

@router.get("/{payment_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
) -> PaymentStatusResponse:
    """Получение статуса платежа"""
    
    # Получаем платеж из БД
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Платеж не найден"
        )
    
    # Если платеж онлайн и не завершен, проверяем статус у провайдера
    if (payment.provider and 
        payment.provider_payment_id and 
        payment.status in ["pending", "processing"]):
        
        manager = get_payment_manager()
        result = manager.check_payment_status(
            payment.provider, 
            payment.provider_payment_id
        )
        
        if result.success and result.status != payment.status:
            # Обновляем статус в БД
            payment.status = result.status
            if result.status == "completed":
                payment.paid_at = datetime.utcnow()
            payment.provider_data = {
                **(payment.provider_data or {}),
                **result.provider_data
            }
            db.commit()
    
    return PaymentStatusResponse(
        payment_id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        created_at=payment.created_at,
        paid_at=payment.paid_at,
        provider_data=payment.provider_data
    )

@router.get("/visit/{visit_id}", response_model=PaymentListResponse)
def get_visit_payments(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
) -> PaymentListResponse:
    """Получение всех платежей по визиту"""
    
    payments = db.query(Payment).filter(Payment.visit_id == visit_id).all()
    
    payment_responses = []
    for payment in payments:
        payment_responses.append(PaymentStatusResponse(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            created_at=payment.created_at,
            paid_at=payment.paid_at,
            provider_data=payment.provider_data
        ))
    
    return PaymentListResponse(
        payments=payment_responses,
        total=len(payment_responses)
    )

@router.post("/{payment_id}/cancel")
def cancel_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """Отмена платежа"""
    
    # Получаем платеж
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Платеж не найден"
        )
    
    # Проверяем возможность отмены
    if payment.status not in ["pending", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Платеж со статусом {payment.status} нельзя отменить"
        )
    
    # Если онлайн-платеж, пытаемся отменить у провайдера
    if payment.provider and payment.provider_payment_id:
        manager = get_payment_manager()
        result = manager.cancel_payment(payment.provider, payment.provider_payment_id)
        
        if result.success:
            payment.status = "cancelled"
            payment.provider_data = {
                **(payment.provider_data or {}),
                **result.provider_data
            }
        else:
            # Даже если провайдер не смог отменить, отмечаем как отмененный в нашей системе
            payment.status = "cancelled"
            payment.provider_data = {
                **(payment.provider_data or {}),
                "cancel_error": result.error_message
            }
    else:
        # Обычный платеж
        payment.status = "cancelled"
    
    db.commit()
    
    return {
        "success": True,
        "payment_id": payment.id,
        "status": payment.status,
        "message": "Платеж отменен"
    }


@router.post("/test-init", response_model=PaymentInitResponse)
def test_init_payment(
    payment_request: PaymentInitRequest,
    db: Session = Depends(get_db)
) -> PaymentInitResponse:
    """Тестовая инициализация платежа БЕЗ аутентификации"""
    
    try:
        # Получаем менеджер провайдеров
        payment_manager = get_payment_manager()
        
        # Создаем запись платежа в БД
        payment = Payment(
            visit_id=payment_request.visit_id,
            amount=payment_request.amount,
            currency=payment_request.currency,
            method="online",
            status="pending",
            provider=payment_request.provider,
            created_at=datetime.utcnow()
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Инициализируем платеж через провайдера
        result = payment_manager.create_payment(
            provider_name=payment_request.provider,
            amount=payment_request.amount,
            currency=payment_request.currency,
            order_id=str(payment.id),
            description=payment_request.description or f"Тестовый платеж #{payment.id}",
            return_url=payment_request.return_url or "http://localhost:5173/payment/success",
            cancel_url=payment_request.cancel_url or "http://localhost:5173/payment/cancel"
        )
        
        if result.success:
            # Обновляем данные платежа
            payment.provider_payment_id = result.payment_id
            payment.payment_url = result.payment_url
            payment.status = "initialized"
            
            db.commit()
            
            return PaymentInitResponse(
                success=True,
                payment_id=payment.id,
                provider=payment_request.provider,
                amount=payment_request.amount,
                currency=payment_request.currency,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id,
                status="initialized",
                message="Тестовый платеж успешно инициализирован"
            )
        else:
            # Ошибка инициализации
            payment.status = "failed"
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка инициализации платежа: {result.error_message}"
            )
            
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка инициализации платежа: {str(e)}"
        )


@router.post("/{payment_id}/receipt")
def generate_receipt(
    payment_id: int,
    format_type: str = "pdf",
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    """Генерация квитанции об оплате"""
    
    try:
        # Получаем платеж
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Платеж не найден"
            )
        
        # Генерируем простую квитанцию
        receipt_data = {
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "created_at": payment.created_at.isoformat(),
            "description": "Оплата медицинских услуг"
        }
        
        # Для демо возвращаем данные квитанции
        return {
            "success": True,
            "receipt_data": receipt_data,
            "receipt_url": f"/api/v1/payments/{payment_id}/receipt/download",
            "format": format_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации квитанции: {str(e)}"
        )


@router.get("/{payment_id}/receipt/download")
def download_receipt(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    """Скачивание квитанции"""
    
    try:
        from fastapi.responses import PlainTextResponse
        
        # Получаем платеж
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Платеж не найден"
            )
        
        # Генерируем текстовую квитанцию
        receipt_content = f"""
КВИТАНЦИЯ ОБ ОПЛАТЕ
===================

Номер платежа: {payment.id}
Дата: {payment.created_at.strftime('%d.%m.%Y %H:%M')}
Сумма: {payment.amount} {payment.currency}
Провайдер: {payment.provider.title()}
Статус: {payment.status.title()}

Описание: Оплата медицинских услуг

Спасибо за использование наших услуг!
        """.strip()
        
        return PlainTextResponse(
            content=receipt_content,
            headers={
                "Content-Disposition": f"attachment; filename=receipt_{payment_id}.txt"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка скачивания квитанции: {str(e)}"
        )


# ===================== ЭНДПОИНТЫ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================

@router.post("/invoice/create", response_model=PaymentInvoiceResponse)
async def create_payment_invoice(
    request: PaymentInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_user)
):
    """Создание счета для оплаты из модуля оплаты"""
    try:
        from app.models.payment_invoice import PaymentInvoice
        
        # Создаем новый счет
        invoice = PaymentInvoice(
            amount=request.amount,
            currency=request.currency,
            provider=request.provider,
            status="pending",
            description=request.description,
            payment_method=request.provider,
            created_by_id=current_user.id
        )
        
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        
        return PaymentInvoiceResponse(
            invoice_id=invoice.id,
            amount=invoice.amount,
            currency=invoice.currency,
            provider=invoice.provider,
            status=invoice.status,
            description=invoice.description,
            created_at=invoice.created_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания счета: {str(e)}"
        )


@router.get("/invoices/pending", response_model=List[PaymentInvoiceResponse])
async def get_pending_invoices(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_user)
):
    """Получение списка неоплаченных счетов"""
    try:
        from app.models.payment_invoice import PaymentInvoice
        
        # Получаем неоплаченные счета
        invoices = db.query(PaymentInvoice).filter(
            PaymentInvoice.status.in_(["pending", "processing"])
        ).order_by(PaymentInvoice.created_at.desc()).limit(50).all()
        
        return [
            PaymentInvoiceResponse(
                invoice_id=invoice.id,
                amount=invoice.amount,
                currency=invoice.currency,
                provider=invoice.provider,
                status=invoice.status,
                description=invoice.description,
                created_at=invoice.created_at
            )
            for invoice in invoices
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения счетов: {str(e)}"
        )