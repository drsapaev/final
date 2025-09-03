#!/usr/bin/env python3
"""
Скрипт для инициализации провайдеров платежей
"""
import os
import sys
from datetime import datetime

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.crud.payment_webhook import create_provider
from app.db.session import get_db
from app.schemas.payment_webhook import PaymentProviderCreate


def init_payment_providers():
    """Инициализируем провайдеров платежей"""
    print("🚀 Инициализация провайдеров платежей...")

    db = next(get_db())

    try:
        # Список провайдеров для инициализации
        providers = [
            {
                "name": "Payme",
                "code": "payme",
                "is_active": True,
                "webhook_url": "https://your-domain.com/api/v1/webhooks/payment/payme",
                "commission_percent": 2,  # 2% комиссия
                "min_amount": 1000,  # 10 сум
                "max_amount": 10000000,  # 100,000 сум
            },
            {
                "name": "Click",
                "code": "click",
                "is_active": True,
                "webhook_url": "https://your-domain.com/api/v1/webhooks/payment/click",
                "commission_percent": 1,  # 1% комиссия
                "min_amount": 1000,  # 10 сум
                "max_amount": 10000000,  # 100,000 сум
            },
            {
                "name": "UzCard",
                "code": "uzcard",
                "is_active": False,  # Пока неактивен
                "webhook_url": "https://your-domain.com/api/v1/webhooks/payment/uzcard",
                "commission_percent": 1,  # 1% комиссия
                "min_amount": 1000,  # 10 сум
                "max_amount": 10000000,  # 100,000 сум
            },
        ]

        created_count = 0
        updated_count = 0

        for provider_data in providers:
            # Проверяем, существует ли уже провайдер
            from app.crud.payment_webhook import get_provider_by_code

            existing = get_provider_by_code(db, code=provider_data["code"])

            if existing:
                print(f"✅ Провайдер {provider_data['name']} уже существует")
                updated_count += 1
            else:
                # Создаём нового провайдера
                provider_create = PaymentProviderCreate(**provider_data)
                new_provider = create_provider(db, provider_create)
                print(f"✅ Создан провайдер: {new_provider.name} ({new_provider.code})")
                created_count += 1

        db.commit()

        print(f"\n🎉 Инициализация завершена!")
        print(f"📊 Создано: {created_count}")
        print(f"📊 Обновлено: {updated_count}")

        # Показываем список всех провайдеров
        print(f"\n📋 Список провайдеров:")
        from app.crud.payment_webhook import get_all_providers

        all_providers = get_all_providers(db)
        for p in all_providers:
            status = "🟢 Активен" if p.is_active else "🔴 Неактивен"
            print(f"  - {p.name} ({p.code}): {status}")

    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_payment_providers()
