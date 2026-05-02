#!/usr/bin/env python3
"""
Тест админ-панели провайдеров оплаты
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session

from app.crud.payment_webhook import (
    create_provider,
    delete_provider,
    get_all_providers,
    get_provider_by_code,
    get_provider_by_id,
    update_provider,
)
from app.db.session import SessionLocal
from app.schemas.payment_webhook import PaymentProviderCreate, PaymentProviderUpdate


def test_providers_crud():
    """Тестируем CRUD операции для провайдеров"""
    db: Session = SessionLocal()

    try:
        print("🧪 Тестирование CRUD операций для провайдеров...")

        # Тест 1: Создание провайдера
        print("\n📝 Тест 1: Создание провайдера")
        import time

        timestamp = int(time.time())
        provider_data = PaymentProviderCreate(
            name=f"Test Payme Provider {timestamp}",
            code=f"test_payme_{timestamp}",
            description="Тестовый провайдер Payme",
            is_active=True,
            secret_key="test_secret_key_123",
            webhook_url="https://example.com/webhook",
            api_url="https://api.payme.uz",
        )

        created_provider = create_provider(db, provider_data)
        print(
            f"✅ Провайдер создан: ID={created_provider.id}, код={created_provider.code}"
        )

        # Тест 2: Получение провайдера по ID
        print(f"\n🔍 Тест 2: Получение провайдера по ID {created_provider.id}")
        retrieved_provider = get_provider_by_id(db, created_provider.id)
        if retrieved_provider:
            print(f"✅ Провайдер найден: {retrieved_provider.name}")
        else:
            print("❌ Провайдер не найден")

        # Тест 3: Получение провайдера по коду
        print(f"\n🔍 Тест 3: Получение провайдера по коду '{created_provider.code}'")
        provider_by_code = get_provider_by_code(db, created_provider.code)
        if provider_by_code:
            print(f"✅ Провайдер найден по коду: {provider_by_code.name}")
        else:
            print("❌ Провайдер не найден по коду")

        # Тест 4: Обновление провайдера
        print(f"\n✏️ Тест 4: Обновление провайдера {created_provider.id}")
        update_data = PaymentProviderUpdate(
            name="Updated Test Payme Provider",
            description="Обновленное описание",
            is_active=False,
        )

        updated_provider = update_provider(db, created_provider.id, update_data)
        if updated_provider:
            print(
                f"✅ Провайдер обновлен: {updated_provider.name}, активен: {updated_provider.is_active}"
            )
        else:
            print("❌ Ошибка обновления провайдера")

        # Тест 5: Получение всех провайдеров
        print("\n📋 Тест 5: Получение всех провайдеров")
        all_providers = get_all_providers(db)
        print(f"✅ Найдено провайдеров: {len(all_providers)}")
        for provider in all_providers:
            print(
                f"   - {provider.name} ({provider.code}) - {'активен' if provider.is_active else 'неактивен'}"
            )

        # Тест 6: Удаление провайдера
        print(f"\n🗑️ Тест 6: Удаление провайдера {created_provider.id}")
        delete_success = delete_provider(db, created_provider.id)
        if delete_success:
            print("✅ Провайдер удален")
        else:
            print("❌ Ошибка удаления провайдера")

        # Проверяем, что провайдер действительно удален
        deleted_provider = get_provider_by_id(db, created_provider.id)
        if not deleted_provider:
            print("✅ Подтверждение: провайдер удален из базы данных")
        else:
            print("❌ Ошибка: провайдер все еще существует в базе данных")

        print("\n🎉 Тестирование CRUD операций завершено!")

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_providers_crud()
