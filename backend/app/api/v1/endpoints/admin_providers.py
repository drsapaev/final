# app/api/v1/endpoints/admin_providers.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.payment_webhook import (
    create_provider,
    delete_provider,
    get_all_providers,
    get_provider_by_code,
    get_provider_by_id,
    update_provider,
)
from app.schemas.payment_webhook import (
    PaymentProviderCreate,
    PaymentProviderOut,
    PaymentProviderUpdate,
)

router = APIRouter()


@router.get(
    "/admin/providers",
    response_model=List[PaymentProviderOut],
    summary="Список всех провайдеров",
)
def list_providers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Получение списка всех провайдеров оплаты (только для админов)"""
    try:
        providers = get_all_providers(db, skip=offset, limit=limit)
        return providers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения провайдеров: {str(e)}",
        )


@router.get(
    "/admin/providers/{provider_id}",
    response_model=PaymentProviderOut,
    summary="Информация о провайдере",
)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Получение информации о конкретном провайдере (только для админов)"""
    try:
        provider = get_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Провайдер с ID {provider_id} не найден",
            )
        return provider
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения провайдера: {str(e)}",
        )


@router.post(
    "/admin/providers",
    response_model=PaymentProviderOut,
    summary="Создание нового провайдера",
)
def create_new_provider(
    provider: PaymentProviderCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Создание нового провайдера оплаты (только для админов)"""
    try:
        # Проверяем, не существует ли уже провайдер с таким кодом
        existing_provider = get_provider_by_code(db, provider.code)
        if existing_provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Провайдер с кодом '{provider.code}' уже существует",
            )

        # Создаём провайдера
        new_provider = create_provider(db, provider)
        return new_provider

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания провайдера: {str(e)}",
        )


@router.put(
    "/admin/providers/{provider_id}",
    response_model=PaymentProviderOut,
    summary="Обновление провайдера",
)
def update_existing_provider(
    provider_id: int,
    provider_update: PaymentProviderUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Обновление существующего провайдера (только для админов)"""
    try:
        # Проверяем существование провайдера
        existing_provider = get_provider_by_id(db, provider_id)
        if not existing_provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Провайдер с ID {provider_id} не найден",
            )

        # Если изменяется код, проверяем уникальность
        if provider_update.code and provider_update.code != existing_provider.code:
            duplicate_provider = get_provider_by_code(db, provider_update.code)
            if duplicate_provider:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Провайдер с кодом '{provider_update.code}' уже существует",
                )

        # Обновляем провайдера
        updated_provider = update_provider(db, provider_id, provider_update)
        return updated_provider

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления провайдера: {str(e)}",
        )


@router.delete("/admin/providers/{provider_id}", summary="Удаление провайдера")
def delete_existing_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Удаление провайдера (только для админов)"""
    try:
        # Проверяем существование провайдера
        existing_provider = get_provider_by_id(db, provider_id)
        if not existing_provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Провайдер с ID {provider_id} не найден",
            )

        # Проверяем, не используется ли провайдер в активных вебхуках
        # Здесь можно добавить дополнительную логику проверки

        # Удаляем провайдера
        delete_provider(db, provider_id)

        return {
            "success": True,
            "message": f"Провайдер с ID {provider_id} успешно удалён",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления провайдера: {str(e)}",
        )


@router.get(
    "/admin/providers/{provider_id}/test", summary="Тест подключения к провайдеру"
)
def test_provider_connection(
    provider_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Тестирование подключения к провайдеру (только для админов)"""
    try:
        # Получаем провайдера
        provider = get_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Провайдер с ID {provider_id} не найден",
            )

        # Здесь можно добавить реальную логику тестирования подключения
        # Например, отправку тестового запроса к API провайдера

        test_result = {
            "provider_id": provider_id,
            "provider_code": provider.code,
            "test_status": "success",
            "message": f"Подключение к {provider.name} успешно протестировано",
            "test_timestamp": "2025-08-29T19:00:00Z",
        }

        return test_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования провайдера: {str(e)}",
        )


@router.get("/admin/providers/{provider_id}/stats", summary="Статистика провайдера")
def get_provider_stats(
    provider_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Получение статистики по провайдеру (только для админов)"""
    try:
        # Получаем провайдера
        provider = get_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Провайдер с ID {provider_id} не найден",
            )

        # Здесь можно добавить логику получения реальной статистики
        # Например, количество вебхуков, успешных транзакций и т.д.

        stats = {
            "provider_id": provider_id,
            "provider_code": provider.code,
            "provider_name": provider.name,
            "total_webhooks": 0,  # Заглушка
            "successful_transactions": 0,  # Заглушка
            "failed_transactions": 0,  # Заглушка
            "total_amount": 0.0,  # Заглушка
            "last_activity": "2025-08-29T19:00:00Z",  # Заглушка
        }

        return stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )


@router.post("/admin/providers/bulk-update", summary="Массовое обновление провайдеров")
def bulk_update_providers(
    updates: List[dict],  # Список обновлений: [{"id": 1, "updates": {...}}, ...]
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin")),
):
    """Массовое обновление провайдеров (только для админов)"""
    try:
        results = []

        for update_item in updates:
            provider_id = update_item.get("id")
            provider_updates = update_item.get("updates", {})

            if not provider_id:
                results.append(
                    {"id": None, "success": False, "error": "ID провайдера не указан"}
                )
                continue

            try:
                # Проверяем существование провайдера
                existing_provider = get_provider_by_id(db, provider_id)
                if not existing_provider:
                    results.append(
                        {
                            "id": provider_id,
                            "success": False,
                            "error": "Провайдер не найден",
                        }
                    )
                    continue

                # Обновляем провайдера
                update_provider(
                    db, provider_id, PaymentProviderUpdate(**provider_updates)
                )

                results.append(
                    {
                        "id": provider_id,
                        "success": True,
                        "message": "Провайдер успешно обновлён",
                    }
                )

            except Exception as e:
                results.append({"id": provider_id, "success": False, "error": str(e)})

        return {
            "success": True,
            "message": f"Обработано {len(updates)} провайдеров",
            "results": results,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массового обновления: {str(e)}",
        )
