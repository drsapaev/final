#!/usr/bin/env python3
"""
Обновление провайдера Payme с тестовым секретным ключом
"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.crud.payment_webhook import get_provider_by_code, update_provider
from app.db.session import get_db
from app.schemas.payment_webhook import PaymentProviderUpdate


def update_payme_provider():
    """Обновляем провайдера Payme"""
    print("🔧 Обновление провайдера Payme")
    print("=" * 50)

    try:
        # Получаем сессию БД
        db = next(get_db())
        print("✅ Подключение к БД установлено")

        # Ищем провайдера Payme
        provider = get_provider_by_code(db, code="payme")
        if not provider:
            print("❌ Провайдер Payme не найден")
            return

        print(f"📋 Найден провайдер: {provider.name} (ID: {provider.id})")
        print(f"🔑 Текущий секретный ключ: {provider.secret_key or 'Не установлен'}")

        # Обновляем секретный ключ на тестовый
        new_secret_key = "test_secret_key_12345"
        update_data = PaymentProviderUpdate(secret_key=new_secret_key)

        updated_provider = update_provider(db, provider.id, update_data)
        if updated_provider:
            print("✅ Провайдер обновлён!")
            print(f"🔑 Новый секретный ключ: {updated_provider.secret_key}")
        else:
            print("❌ Не удалось обновить провайдера")

        db.close()
        print("\n✅ Обновление завершено")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    update_payme_provider()
