# app/api/v1/endpoints/payment_webhook.py

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.payment_webhook import (
    create_provider as crud_create_provider,
)
from app.crud.payment_webhook import (
    delete_provider,
    get_all_providers,
    get_all_transactions,
    get_all_webhooks,
    get_provider_by_id,
    get_transaction_by_id,
    get_webhook_by_id,
)
from app.crud.payment_webhook import (
    update_provider as crud_update_provider,
)
from app.schemas.payment_webhook import (
    PaymentProviderCreate,
    PaymentProviderOut,
    PaymentProviderUpdate,
    PaymentTransactionOut,
    PaymentWebhookOut,
)
from app.services.payment_webhook import payment_webhook_service

router = APIRouter(prefix="/webhooks", tags=["payment_webhooks"])


# --- Webhook endpoints (публичные, без аутентификации) ---


@router.post("/payment/payme", name="payme_webhook")
async def payme_webhook(request: Request, db: Session = Depends(get_db)):
    """Вебхук от Payme для обработки платежей"""
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

        # Обрабатываем вебхук
        success, message, webhook = payment_webhook_service.process_payme_webhook(
            db, data, signature
        )

        if success:
            return {
                "ok": True,
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }
        else:
            # Возвращаем 200 OK даже при ошибке, чтобы Payme не повторял запрос
            return {
                "ok": False,
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }

    except Exception as e:
        # Логируем ошибку, но возвращаем 200 OK
        print(f"❌ Payme webhook error: {e}")
        return {"ok": False, "message": f"Error processing webhook: {str(e)}"}


@router.post("/payment/click", name="click_webhook")
async def click_webhook(request: Request, db: Session = Depends(get_db)):
    """Вебхук от Click для обработки платежей"""
    try:
        # Получаем данные из формы
        form_data = await request.form()
        data = dict(form_data)

        # Обрабатываем вебхук
        success, message, webhook = payment_webhook_service.process_click_webhook(
            db, data
        )

        if success:
            return {
                "ok": True,
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }
        else:
            # Возвращаем 200 OK даже при ошибке
            return {
                "ok": False,
                "message": message,
                "webhook_id": webhook.id if webhook else None,
            }

    except Exception as e:
        # Логируем ошибку, но возвращаем 200 OK
        print(f"❌ Click webhook error: {e}")
        return {"ok": False, "message": f"Error processing webhook: {str(e)}"}


# --- Payment Providers management (Admin only) ---


@router.get(
    "/payment/providers", name="list_providers", response_model=list[PaymentProviderOut]
)
def list_providers(
    db: Session = Depends(get_db), current_user=Depends(require_roles("Admin"))
):
    """Список провайдеров платежей"""
    return get_all_providers(db)


@router.post(
    "/payment/providers", name="create_provider", response_model=PaymentProviderOut
)
def create_provider(
    provider_in: PaymentProviderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Создание нового провайдера платежей"""
    # Проверяем, что код провайдера уникален
    from app.crud.payment_webhook import get_provider_by_code

    existing = get_provider_by_code(db, code=provider_in.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider with code '{provider_in.code}' already exists",
        )

    return crud_create_provider(db, provider_in)


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
    provider = get_provider_by_id(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )
    return provider


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
    provider = get_provider_by_id(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    return crud_update_provider(db, provider_id, provider_in)


@router.delete("/payment/providers/{provider_id}", name="delete_provider")
def delete_provider_endpoint(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
):
    """Удаление провайдера платежей"""
    provider = get_provider_by_id(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    success = delete_provider(db, provider_id)
    if success:
        return {"ok": True, "message": "Provider deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete provider",
        )


# --- Admin endpoints (требуют аутентификации) ---


@router.get("/payment", name="list_webhooks", response_model=list[PaymentWebhookOut])
def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    provider: str = Query(None, description="Фильтр по провайдеру"),
    status: str = Query(None, description="Фильтр по статусу"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Список вебхуков оплат"""
    webhooks = get_all_webhooks(db, skip=skip, limit=limit)

    # Применяем фильтры
    if provider:
        webhooks = [w for w in webhooks if w.provider == provider]
    if status:
        webhooks = [w for w in webhooks if w.status == status]

    return webhooks


@router.get(
    "/payment/transactions",
    name="list_transactions",
    response_model=list[PaymentTransactionOut],
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
    try:
        print(f"🔍 Получаем транзакции: skip={skip}, limit={limit}")
        transactions = get_all_transactions(db, skip=skip, limit=limit)
        print(f"📊 Получено транзакций: {len(transactions)}")

        # Применяем фильтры
        if provider:
            transactions = [t for t in transactions if t.provider == provider]
            print(f"🔍 После фильтра по провайдеру: {len(transactions)}")
        if status:
            transactions = [t for t in transactions if t.status == status]
            print(f"🔍 После фильтра по статусу: {len(transactions)}")
        if visit_id:
            transactions = [t for t in transactions if t.visit_id == visit_id]
            print(f"🔍 После фильтра по визиту: {len(transactions)}")

        print(f"✅ Возвращаем {len(transactions)} транзакций")
        return transactions
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
    try:
        print(f"📊 Получаем сводку вебхуков для провайдера: {provider}")
        summary = payment_webhook_service.get_webhook_summary(db, provider)
        print(f"✅ Сводка получена: {summary}")
        return summary
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
    transaction = get_transaction_by_id(db, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    return transaction


@router.get(
    "/payment/{webhook_id}", name="get_webhook", response_model=PaymentWebhookOut
)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar")),
):
    """Получение вебхука по ID"""
    webhook = get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )
    return webhook
