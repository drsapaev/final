#!/usr/bin/env python3
"""
Тест интеграции вебхуков с записями (appointments)
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.payment_webhook import PaymentWebhookOut
from app.services.visit_payment_integration import VisitPaymentIntegrationService


def test_payment_integration():
    """Тестируем интеграцию платежей с записями"""
    db: Session = SessionLocal()

    try:
        print("🧪 Тестирование интеграции вебхуков с записями...")

        # Создаём тестовый вебхук
        test_webhook = PaymentWebhookOut(
            id=999,
            provider="payme",
            webhook_id="test_webhook_123",
            transaction_id="test_transaction_456",
            amount=50000,  # 500.00 UZS в тийинах
            currency="UZS",
            status="processed",
            raw_data={"test": "data"},
            signature="test_signature",
            error_message=None,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
        )

        print("✅ Тестовый вебхук создан")

        # Тест 1: Создание записи на основе платежа
        print("\n📝 Тест 1: Создание записи на основе платежа")
        success, message, appointment_id = (
            VisitPaymentIntegrationService.create_appointment_from_payment(
                db=db,
                webhook=test_webhook,
                patient_id=1,  # Предполагаем, что пациент с ID=1 существует
                doctor_id=1,  # Предполагаем, что врач с ID=1 существует
                department="General",
                appointment_date="2025-01-30",
                appointment_time="10:00",
            )
        )

        if success:
            print(f"✅ Запись {appointment_id} создана успешно: {message}")
        else:
            print(f"❌ Ошибка создания записи: {message}")

        # Тест 2: Обработка платежа для существующей записи
        if success and appointment_id:
            print(f"\n💰 Тест 2: Обработка платежа для записи {appointment_id}")
            success2, message2 = (
                VisitPaymentIntegrationService.process_payment_for_appointment(
                    db=db, appointment_id=appointment_id, webhook=test_webhook
                )
            )

            if success2:
                print(f"✅ Платёж для записи {appointment_id} обработан: {message2}")
            else:
                print(f"❌ Ошибка обработки платежа: {message2}")

        # Тест 3: Получение информации о платеже
        if success and appointment_id:
            print(
                f"\n📊 Тест 3: Получение информации о платеже для записи {appointment_id}"
            )
            success3, message3, payment_info = (
                VisitPaymentIntegrationService.get_visit_payment_info(
                    db=db,
                    visit_id=appointment_id,  # Используем appointment_id как visit_id для теста
                )
            )

            if success3:
                print(f"✅ Информация о платеже получена: {message3}")
                print(f"   Статус платежа: {payment_info.get('payment_status')}")
                print(
                    f"   Сумма: {payment_info.get('payment_amount')} {payment_info.get('payment_currency')}"
                )
                print(f"   Провайдер: {payment_info.get('payment_provider')}")
            else:
                print(f"❌ Ошибка получения информации о платеже: {message3}")

        print("\n🎉 Тестирование завершено!")

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_payment_integration()
