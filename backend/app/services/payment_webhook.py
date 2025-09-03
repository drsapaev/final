# app/services/payment_webhook.py
import hashlib
import hmac
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.crud.payment_webhook import (
    count_transactions,
    count_webhooks,
    create_transaction,
    create_webhook,
    get_failed_webhooks,
    get_pending_webhooks,
    get_provider_by_code,
    get_transactions_by_status,
    get_webhook_by_webhook_id,
    update_webhook,
)
from app.models.payment_webhook import PaymentWebhook
from app.schemas.payment_webhook import (
    ClickWebhookData,
    PaymentTransactionCreate,
    PaymentWebhookCreate,
    PaymeWebhookData,
)
from app.services.visit_payment_integration import VisitPaymentIntegrationService


class PaymentWebhookService:
    """Сервис для обработки вебхуков оплат"""

    @staticmethod
    def verify_payme_signature(
        data: Dict[str, Any], signature: str, secret_key: str
    ) -> bool:
        """Верификация подписи Payme"""
        try:
            # Сортируем ключи по алфавиту
            sorted_data = dict(sorted(data.items()))

            # Создаём строку для подписи
            sign_string = ""
            for key, value in sorted_data.items():
                if key != "signature" and value is not None:
                    sign_string += f"{key}={value};"

            # Убираем последний символ ";"
            sign_string = sign_string.rstrip(";")

            # Создаём подпись
            expected_signature = hmac.new(
                secret_key.encode("utf-8"), sign_string.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            return signature.lower() == expected_signature.lower()
        except Exception:
            return False

    @staticmethod
    def verify_click_signature(data: Dict[str, Any], secret_key: str) -> bool:
        """Верификация подписи Click"""
        try:
            # Создаём строку для подписи
            sign_string = f"{data['click_trans_id']}{data['service_id']}{data['merchant_trans_id']}{data['amount']}{data['action']}{data['sign_time']}"

            # Создаём подпись
            expected_signature = hashlib.md5(sign_string.encode("utf-8")).hexdigest()

            return data["sign_string"] == expected_signature
        except Exception:
            return False

    @staticmethod
    def process_payme_webhook(
        db: Session, data: Dict[str, Any], signature: str
    ) -> Tuple[bool, str, Optional[PaymentWebhook]]:
        """Обработка вебхука от Payme"""
        try:
            # Парсим данные
            webhook_data = PaymeWebhookData(**data)

            # Получаем провайдера
            provider = get_provider_by_code(db, code="payme")
            if not provider:
                return False, "Provider not found", None

            # Верифицируем подпись
            if not PaymentWebhookService.verify_payme_signature(
                data, signature, provider.secret_key
            ):
                return False, "Invalid signature", None

            # Проверяем, не обработан ли уже этот вебхук
            existing_webhook = get_webhook_by_webhook_id(db, webhook_id=webhook_data.id)
            if existing_webhook:
                return False, "Webhook already processed", existing_webhook

            # Определяем статус
            status_map = {1: "pending", 2: "processed", -1: "failed", -2: "failed"}
            status = status_map.get(webhook_data.state, "pending")

            # Создаём вебхук
            webhook_create = PaymentWebhookCreate(
                provider="payme",
                webhook_id=webhook_data.id,
                transaction_id=webhook_data.id,
                amount=webhook_data.amount,
                currency="UZS",
                raw_data=data,
                signature=signature,
                status="pending",  # Устанавливаем начальный статус
            )

            webhook = create_webhook(db, webhook_create)

            # Создаём транзакцию
            transaction_create = PaymentTransactionCreate(
                transaction_id=webhook_data.id,
                provider="payme",
                amount=webhook_data.amount,
                currency="UZS",
                status=status,
                webhook_id=webhook.id,
            )

            transaction = create_transaction(db, transaction_create)

            # Обновляем статус вебхука
            webhook_update = {"status": status, "processed_at": datetime.utcnow()}
            if status == "failed":
                webhook_update["error_message"] = f"Payme state: {webhook_data.state}"

            update_webhook(db, webhook.id, webhook_update)

            # Интеграция с записями и визитами - если платёж успешен
            if status == "processed":
                try:
                    # Извлекаем ID записи или визита из данных вебхука
                    appointment_id = None
                    visit_id = None

                    if hasattr(webhook_data, "account") and webhook_data.account:
                        # Пытаемся найти appointment_id или visit_id в account данных
                        if hasattr(webhook_data.account, "appointment_id"):
                            appointment_id = int(webhook_data.account.appointment_id)
                        elif hasattr(webhook_data.account, "visit_id"):
                            visit_id = int(webhook_data.account.visit_id)
                        elif hasattr(webhook_data.account, "order_id"):
                            # Если есть order_id, пытаемся интерпретировать как appointment_id
                            try:
                                appointment_id = int(webhook_data.account.order_id)
                            except (ValueError, TypeError):
                                pass

                    # Приоритет: сначала ищем appointment_id, потом visit_id
                    if appointment_id:
                        # Обрабатываем платёж для существующей записи
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_appointment(
                                db, appointment_id, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Платёж для записи {appointment_id} обработан: {message}"
                            )
                        else:
                            print(
                                f"⚠️ Ошибка обработки платежа для записи {appointment_id}: {message}"
                            )
                    elif visit_id:
                        # Обновляем существующий визит
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_existing_visit(
                                db, visit_id, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Платёж для визита {visit_id} обработан: {message}"
                            )
                        else:
                            print(
                                f"⚠️ Ошибка обработки платежа для визита {visit_id}: {message}"
                            )
                    else:
                        # Создаём новую запись на основе платежа
                        success, message, new_appointment_id = (
                            VisitPaymentIntegrationService.create_appointment_from_payment(
                                db, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Создана новая запись {new_appointment_id} на основе платежа: {message}"
                            )
                        else:
                            print(f"⚠️ Ошибка создания записи: {message}")

                except Exception as e:
                    print(f"⚠️ Ошибка интеграции с записями/визитами: {e}")
                    # Не прерываем обработку вебхука из-за ошибки интеграции

            return True, "Webhook processed successfully", webhook

        except Exception as e:
            return False, f"Error processing webhook: {str(e)}", None

    @staticmethod
    def process_click_webhook(
        db: Session, data: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[PaymentWebhook]]:
        """Обработка вебхука от Click"""
        try:
            # Парсим данные
            webhook_data = ClickWebhookData(**data)

            # Получаем провайдера
            provider = get_provider_by_code(db, code="click")
            if not provider:
                return False, "Provider not found", None

            # Верифицируем подпись
            if not PaymentWebhookService.verify_click_signature(
                data, provider.secret_key
            ):
                return False, "Invalid signature", None

            # Проверяем, не обработан ли уже этот вебхук
            existing_webhook = get_webhook_by_webhook_id(
                db, webhook_id=webhook_data.click_trans_id
            )
            if existing_webhook:
                return False, "Webhook already processed", existing_webhook

            # Определяем статус
            status = "success" if webhook_data.action == "0" else "failed"

            # Создаём вебхук
            webhook_create = PaymentWebhookCreate(
                provider="click",
                webhook_id=webhook_data.click_trans_id,
                transaction_id=webhook_data.merchant_trans_id,
                amount=int(float(webhook_data.amount) * 100),  # Конвертируем в тийины
                currency="UZS",
                raw_data=data,
                status="pending",  # Устанавливаем начальный статус
            )

            webhook = create_webhook(db, webhook_create)

            # Создаём транзакцию
            transaction_create = PaymentTransactionCreate(
                transaction_id=webhook_data.merchant_trans_id,
                provider="click",
                amount=int(float(webhook_data.amount) * 100),
                currency="UZS",
                status=status,
                webhook_id=webhook.id,
            )

            transaction = create_transaction(db, transaction_create)

            # Обновляем статус вебхука
            webhook_update = {"status": status, "processed_at": datetime.utcnow()}
            if status == "failed":
                webhook_update["error_message"] = f"Click error: {webhook_data.error}"

            update_webhook(db, webhook.id, webhook_update)

            # Интеграция с записями и визитами - если платёж успешен
            if status == "success":
                try:
                    # Извлекаем ID записи или визита из данных вебхука
                    appointment_id = None
                    visit_id = None

                    if hasattr(webhook_data, "merchant_trans_id"):
                        # Пытаемся найти appointment_id или visit_id в merchant_trans_id
                        try:
                            # Предполагаем, что merchant_trans_id может быть appointment_id
                            appointment_id = int(webhook_data.merchant_trans_id)
                        except (ValueError, TypeError):
                            # Если merchant_trans_id не является числом, пропускаем
                            pass

                    # Приоритет: сначала ищем appointment_id, потом visit_id
                    if appointment_id:
                        # Обрабатываем платёж для существующей записи
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_appointment(
                                db, appointment_id, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Платёж для записи {appointment_id} обработан: {message}"
                            )
                        else:
                            print(
                                f"⚠️ Ошибка обработки платежа для записи {appointment_id}: {message}"
                            )
                    elif visit_id:
                        # Обновляем существующий визит
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_existing_visit(
                                db, visit_id, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Платёж для визита {visit_id} обработан: {message}"
                            )
                        else:
                            print(
                                f"⚠️ Ошибка обработки платежа для визита {visit_id}: {message}"
                            )
                    else:
                        # Создаём новую запись на основе платежа
                        success, message, new_appointment_id = (
                            VisitPaymentIntegrationService.create_appointment_from_payment(
                                db, webhook
                            )
                        )
                        if success:
                            print(
                                f"✅ Создана новая запись {new_appointment_id} на основе платежа: {message}"
                            )
                        else:
                            print(f"⚠️ Ошибка создания записи: {message}")

                except Exception as e:
                    print(f"⚠️ Ошибка интеграции с записями/визитами: {e}")
                    # Не прерываем обработку вебхука из-за ошибки интеграции

            return True, "Webhook processed successfully", webhook

        except Exception as e:
            return False, f"Error processing webhook: {str(e)}", None

    @staticmethod
    def get_webhook_summary(
        db: Session, provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение сводки по вебхукам"""
        try:
            # Используем глобальные импорты
            total_webhooks = count_webhooks(db)
            pending_webhooks = len(get_pending_webhooks(db))
            failed_webhooks = len(get_failed_webhooks(db))

            total_transactions = count_transactions(db)
            successful_transactions = len(
                get_transactions_by_status(db, status="success")
            )
            failed_transactions = len(get_transactions_by_status(db, status="failed"))

            return {
                "webhooks": {
                    "total": total_webhooks,
                    "pending": pending_webhooks,
                    "failed": failed_webhooks,
                },
                "transactions": {
                    "total": total_transactions,
                    "successful": successful_transactions,
                    "failed": failed_transactions,
                },
            }
        except Exception as e:
            print(f"❌ Ошибка в get_webhook_summary: {e}")
            return {"error": str(e)}


# Создаём экземпляр сервиса
payment_webhook_service = PaymentWebhookService()
