# app/api/v1/endpoints/payment_webhook.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.schemas.payment_webhook import (
    PaymentProviderCreate,
    PaymentProviderOut,
    PaymentProviderUpdate,
    PaymentTransactionOut,
    PaymentWebhookOut,
)
from app.services.payment_webhook_api_service import (
    PaymentWebhookApiDomainError,
    PaymentWebhookApiService,
)

router = APIRouter(prefix="/webhooks", tags=["payment_webhooks"])


# --- Webhook endpoints (публичные, без аутентификации) ---


@router.post("/payment/payme", name="payme_webhook")
async def payme_webhook(request: Request, db: Session = Depends(get_db)):
    """Вебхук от Payme для обработки платежей"""
    service = PaymentWebhookApiService(db)
    try:
        # Получаем данные из запроса
        data = await request.json()

        # Получаем подпись из заголовков
        signature = request.headers.get("X-Payme-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-Payme-Signature header",
            )

        return service.process_payme_webhook(data=data, signature=signature)

    except Exception as e:
        # Логируем ошибку, но возвращаем 200 OK
        print(f"❌ Payme webhook error: {e}")
        return {"ok": False, "message": f"Error processing webhook: {str(e)}"}


@router.post("/payment/click", name="click_webhook")
async def click_webhook(request: Request, db: Session = Depends(get_db)):
    """Вебхук от Click для обработки платежей"""
    service = PaymentWebhookApiService(db)
    try:
        # Получаем данные из формы
        form_data = await request.form()
        data = dict(form_data)
        return service.process_click_webhook(data=data)

    except Exception as e:
        # Логируем ошибку, но возвращаем 200 OK
        print(f"❌ Click webhook error: {e}")
        return {"ok": False, "message": f"Error processing webhook: {str(e)}"}


# --- Payment Providers management (Admin only) ---


@router.get(
    "/payment/providers", name="list_providers", response_model=List[PaymentProviderOut]
)
def list_providers(
    db: Session = Depends(get_db), current_user=Depends(require_roles("Admin"))
):
    """Список провайдеров платежей"""
    return PaymentWebhookApiService(db).list_providers()


@router.post(
    "/payment/providers", name="create_provider", response_model=PaymentProviderOut
)
def create_provider(
    provider_in: PaymentProviderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Создание нового провайдера платежей"""
    service = PaymentWebhookApiService(db)
    try:
        return service.create_provider(provider_in)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/payment/providers/{provider_id}",
    name="get_provider",
    response_model=PaymentProviderOut,
)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Получение провайдера по ID"""
    service = PaymentWebhookApiService(db)
    try:
        return service.get_provider(provider_id)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.put(
    "/payment/providers/{provider_id}",
    name="update_provider",
    response_model=PaymentProviderOut,
)
def update_provider(
    provider_id: int,
    provider_in: PaymentProviderUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Обновление провайдера платежей"""
    service = PaymentWebhookApiService(db)
    try:
        return service.update_provider(provider_id, provider_in)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("/payment/providers/{provider_id}", name="delete_provider")
def delete_provider_endpoint(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Удаление провайдера платежей"""
    service = PaymentWebhookApiService(db)
    try:
        return service.delete_provider(provider_id)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# --- Admin endpoints (требуют аутентификации) ---


@router.get("/payment", name="list_webhooks", response_model=List[PaymentWebhookOut])
def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    provider: str = Query(None, description="Фильтр по провайдеру"),
    status: str = Query(None, description="Фильтр по статусу"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Список вебхуков оплат"""
    service = PaymentWebhookApiService(db)
    return service.list_webhooks(
        skip=skip,
        limit=limit,
        provider=provider,
        status=status,
    )


@router.get(
    "/payment/transactions",
    name="list_transactions",
    response_model=List[PaymentTransactionOut],
)
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    provider: str = Query(None, description="Фильтр по провайдеру"),
    status: str = Query(None, description="Фильтр по статусу"),
    visit_id: int = Query(None, description="Фильтр по ID визита"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Список транзакций оплат"""
    service = PaymentWebhookApiService(db)
    try:
        return service.list_transactions(
            skip=skip,
            limit=limit,
            provider=provider,
            status=status,
            visit_id=visit_id,
        )
    except Exception as e:
        print(f"❌ Ошибка в list_transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting transactions: {str(e)}",
        )


@router.get("/payment/summary", name="webhook_summary")
def get_webhook_summary(
    provider: str = Query(None, description="Фильтр по провайдеру"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Сводка по вебхукам и транзакциям"""
    service = PaymentWebhookApiService(db)
    try:
        return service.get_webhook_summary(provider=provider)
    except Exception as e:
        print(f"❌ Ошибка в get_webhook_summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting summary: {str(e)}",
        )


@router.get(
    "/payment/transactions/{transaction_id}",
    name="get_transaction",
    response_model=PaymentTransactionOut,
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Получение транзакции по ID"""
    service = PaymentWebhookApiService(db)
    try:
        return service.get_transaction(transaction_id)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/payment/{webhook_id}", name="get_webhook", response_model=PaymentWebhookOut
)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Получение вебхука по ID"""
    service = PaymentWebhookApiService(db)
    try:
        return service.get_webhook(webhook_id)
    except PaymentWebhookApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
