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


def _get_required_payme_secret_key():
    secret_key = os.getenv("PAYME_PROVIDER_SECRET_KEY") or os.getenv("PAYME_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "Set PAYME_PROVIDER_SECRET_KEY or PAYME_SECRET_KEY before running this script."
        )
    return secret_key


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
        print(
            f"🔑 Текущий секретный ключ: {'Установлен' if provider.secret_key else 'Не установлен'}"
        )

        # Обновляем секретный ключ из локального env
        new_secret_key = _get_required_payme_secret_key()
        update_data = PaymentProviderUpdate(secret_key=new_secret_key)

        updated_provider = update_provider(db, provider.id, update_data)
        if updated_provider:
            print("✅ Провайдер обновлён!")
            print("🔑 Новый секретный ключ: установлен из env")
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
