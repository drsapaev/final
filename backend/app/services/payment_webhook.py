# app/services/payment_webhook.py
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.payment_webhook import PaymentWebhook
from app.repositories.payment_webhook_processing_repository import (
    PaymentWebhookProcessingRepository,
)
from app.schemas.payment_webhook import (
    ClickWebhookData,
    PaymentTransactionCreate,
    PaymentWebhookCreate,
    PaymeWebhookData,
)
from app.services.visit_payment_integration import VisitPaymentIntegrationService

logger = logging.getLogger(__name__)


class PaymentWebhookService:
    """Payment webhook processing service."""

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _account_value(account: Any, key: str) -> Any:
        if isinstance(account, dict):
            return account.get(key)
        return getattr(account, key, None)

    @staticmethod
    def _resolve_payme_account_targets(
        db: Session,
        account: Any,
    ) -> tuple[int | None, int | None, bool]:
        appointment_id = PaymentWebhookService._optional_int(
            PaymentWebhookService._account_value(account, "appointment_id")
        )
        visit_id = PaymentWebhookService._optional_int(
            PaymentWebhookService._account_value(account, "visit_id")
        )
        if appointment_id is not None or visit_id is not None:
            return appointment_id, visit_id, False

        order_id = PaymentWebhookService._optional_int(
            PaymentWebhookService._account_value(account, "order_id")
        )
        if order_id is None:
            return None, None, False

        target_type, target_id = (
            PaymentWebhookService._resolve_numeric_appointment_or_visit_target(
                db, order_id
            )
        )
        if target_type == "ambiguous":
            return None, None, True
        if target_type == "visit":
            return None, target_id, False
        return target_id, None, False

    @staticmethod
    def _payme_targets_cross_patient(
        db: Session, appointment_id: int, visit_id: int
    ) -> bool:
        from app.models.appointment import Appointment
        from app.models.visit import Visit

        appointment_patient_id = (
            db.query(Appointment.patient_id)
            .filter(Appointment.id == appointment_id)
            .scalar()
        )
        visit_patient_id = (
            db.query(Visit.patient_id).filter(Visit.id == visit_id).scalar()
        )

        if appointment_patient_id is None or visit_patient_id is None:
            return False
        return int(appointment_patient_id) != int(visit_patient_id)

    @staticmethod
    def _resolve_numeric_appointment_or_visit_target(
        db: Session, target_value: Any
    ) -> tuple[str | None, int | None]:
        target_id = PaymentWebhookService._optional_int(target_value)
        if target_id is None:
            return None, None

        from app.models.appointment import Appointment
        from app.models.visit import Visit

        appointment_exists = (
            db.query(Appointment.id).filter(Appointment.id == target_id).first()
            is not None
        )
        visit_exists = (
            db.query(Visit.id).filter(Visit.id == target_id).first() is not None
        )

        if appointment_exists and visit_exists:
            return "ambiguous", target_id
        if visit_exists:
            return "visit", target_id
        return "appointment", target_id

    @staticmethod
    def _resolve_click_merchant_target(
        db: Session, merchant_trans_id: Any
    ) -> tuple[str | None, int | None]:
        return PaymentWebhookService._resolve_numeric_appointment_or_visit_target(
            db, merchant_trans_id
        )

    @staticmethod
    def verify_payme_signature(
        data: dict[str, Any], signature: str, secret_key: str
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

            return hmac.compare_digest(signature.lower(), expected_signature.lower())
        except Exception:
            return False

    @staticmethod
    def verify_click_signature(data: dict[str, Any], secret_key: str) -> bool:
        """Верификация подписи Click"""
        try:
            # Создаём строку для подписи
            fields = [
                "click_trans_id",
                "service_id",
                "merchant_id",
                "amount",
                "action",
                "error",
                "error_note",
                "sign_time",
            ]
            sign_string = "".join(str(data.get(field, "")) for field in fields)
            sign_string += secret_key

            # Создаём подпись
            expected_signature = hashlib.md5(sign_string.encode("utf-8"), usedforsecurity=False).hexdigest()

            return hmac.compare_digest(data["sign_string"], expected_signature)
        except Exception:
            return False

    @staticmethod
    def process_payme_webhook(
        db: Session, data: dict[str, Any], signature: str
    ) -> tuple[bool, str, PaymentWebhook | None]:
        """Обработка вебхука от Payme"""
        try:
            repository = PaymentWebhookProcessingRepository(db)
            # Парсим данные
            webhook_data = PaymeWebhookData(**data)

            # Получаем провайдера
            provider = repository.get_provider_by_code("payme")
            if not provider:
                return False, "Provider not found", None

            # Верифицируем подпись
            if not PaymentWebhookService.verify_payme_signature(
                data, signature, provider.secret_key
            ):
                return False, "Invalid signature", None

            # Проверяем, не обработан ли уже этот вебхук
            existing_webhook = repository.get_webhook_by_webhook_id(webhook_data.id)
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

            webhook = repository.create_webhook(webhook_create)

            # Создаём транзакцию
            transaction_create = PaymentTransactionCreate(
                transaction_id=webhook_data.id,
                provider="payme",
                amount=webhook_data.amount,
                currency="UZS",
                status=status,
                webhook_id=webhook.id,
            )

            repository.create_transaction(transaction_create)

            # Обновляем статус вебхука
            webhook_update = {"status": status, "processed_at": datetime.utcnow()}
            if status == "failed":
                webhook_update["error_message"] = f"Payme state: {webhook_data.state}"

            repository.update_webhook(webhook.id, webhook_update)

            # Интеграция с записями и визитами - если платёж успешен
            if status == "processed":
                try:
                    # Извлекаем ID записи или визита из данных вебхука
                    appointment_id = None
                    visit_id = None

                    ambiguous_order_id = False
                    if hasattr(webhook_data, "account") and webhook_data.account:
                        appointment_id, visit_id, ambiguous_order_id = (
                            PaymentWebhookService._resolve_payme_account_targets(
                                db, webhook_data.account
                            )
                        )
                        logger.info(
                            "payment_webhook_payme_account_targets_extracted",
                            extra={
                                "payment_provider": "payme",
                                "webhook_record_id": webhook.id,
                                "has_appointment_target": appointment_id is not None,
                                "has_visit_target": visit_id is not None,
                                "ambiguous_order_id": ambiguous_order_id,
                            },
                        )

                    # Приоритет: сначала ищем appointment_id, потом visit_id
                    if ambiguous_order_id:
                        repository.update_webhook(
                            webhook.id,
                            {
                                "status": "failed",
                                "processed_at": datetime.utcnow(),
                                "error_message": (
                                    "Ambiguous Payme account order_id matches both "
                                    "Appointment.id and Visit.id"
                                ),
                            },
                        )
                        logger.warning(
                            "payment_webhook_payme_ambiguous_account_order_id",
                            extra={
                                "payment_provider": "payme",
                                "webhook_record_id": webhook.id,
                            },
                        )
                        return True, "Webhook processed successfully", webhook

                    if (
                        appointment_id is not None
                        and visit_id is not None
                        and PaymentWebhookService._payme_targets_cross_patient(
                            db, appointment_id, visit_id
                        )
                    ):
                        repository.update_webhook(
                            webhook.id,
                            {
                                "status": "failed",
                                "processed_at": datetime.utcnow(),
                                "error_message": (
                                    "Payme account appointment_id and visit_id "
                                    "belong to different patients"
                                ),
                            },
                        )
                        logger.warning(
                            "payment_webhook_payme_conflicting_account_targets",
                            extra={
                                "payment_provider": "payme",
                                "webhook_record_id": webhook.id,
                            },
                        )
                        return True, "Webhook processed successfully", webhook

                    if appointment_id:
                        # Обрабатываем платёж для существующей записи
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_appointment(
                                db, appointment_id, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "appointment",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "appointment",
                                },
                            )
                    elif visit_id:
                        # Обновляем существующий визит
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_existing_visit(
                                db, visit_id, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "visit",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "visit",
                                },
                            )
                    else:
                        # Создаём новую запись на основе платежа
                        success, message, new_appointment_id = (
                            VisitPaymentIntegrationService.create_appointment_from_payment(
                                db, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "new_appointment",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "payme",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "new_appointment",
                                },
                            )

                except Exception as exc:
                    logger.error(
                        "payment_webhook_visit_integration_exception",
                        extra={
                            "payment_provider": "payme",
                            "webhook_record_id": webhook.id,
                            "exception_type": type(exc).__name__,
                        },
                    )
                    # Не прерываем обработку вебхука из-за ошибки интеграции

            return True, "Webhook processed successfully", webhook

        except Exception as exc:
            logger.error(
                "payment_webhook_processing_exception",
                extra={
                    "payment_provider": "payme",
                    "exception_type": type(exc).__name__,
                },
            )
            return False, "Error processing webhook", None

    @staticmethod
    def process_click_webhook(
        db: Session, data: dict[str, Any]
    ) -> tuple[bool, str, PaymentWebhook | None]:
        """Обработка вебхука от Click"""
        try:
            repository = PaymentWebhookProcessingRepository(db)
            # Парсим данные
            webhook_data = ClickWebhookData(**data)

            # Получаем провайдера
            provider = repository.get_provider_by_code("click")
            if not provider:
                return False, "Provider not found", None

            # Верифицируем подпись
            if not PaymentWebhookService.verify_click_signature(
                data, provider.secret_key
            ):
                return False, "Invalid signature", None

            # Проверяем, не обработан ли уже этот вебхук
            existing_webhook = repository.get_webhook_by_webhook_id(
                webhook_data.click_trans_id
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

            webhook = repository.create_webhook(webhook_create)

            # Создаём транзакцию
            transaction_create = PaymentTransactionCreate(
                transaction_id=webhook_data.merchant_trans_id,
                provider="click",
                amount=int(float(webhook_data.amount) * 100),
                currency="UZS",
                status=status,
                webhook_id=webhook.id,
            )

            repository.create_transaction(transaction_create)

            # Обновляем статус вебхука
            webhook_update = {"status": status, "processed_at": datetime.utcnow()}
            if status == "failed":
                webhook_update["error_message"] = f"Click error: {webhook_data.error}"

            repository.update_webhook(webhook.id, webhook_update)

            # Интеграция с записями и визитами - если платёж успешен
            if status == "success":
                try:
                    # Извлекаем ID записи или визита из данных вебхука
                    target_type, target_id = (
                        PaymentWebhookService._resolve_click_merchant_target(
                            db, webhook_data.merchant_trans_id
                        )
                    )
                    appointment_id = target_id if target_type == "appointment" else None
                    visit_id = target_id if target_type == "visit" else None

                    # Приоритет: сначала ищем appointment_id, потом visit_id
                    if target_type == "ambiguous":
                        repository.update_webhook(
                            webhook.id,
                            {
                                "status": "failed",
                                "processed_at": datetime.utcnow(),
                                "error_message": (
                                    "Ambiguous Click merchant_trans_id matches both "
                                    "Appointment.id and Visit.id"
                                ),
                            },
                        )
                        logger.warning(
                            "payment_webhook_click_ambiguous_merchant_target",
                            extra={
                                "payment_provider": "click",
                                "webhook_record_id": webhook.id,
                                "merchant_trans_id": webhook_data.merchant_trans_id,
                            },
                        )
                    elif appointment_id:
                        # Обрабатываем платёж для существующей записи
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_appointment(
                                db, appointment_id, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "appointment",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "appointment",
                                },
                            )
                    elif visit_id:
                        # Обновляем существующий визит
                        success, message = (
                            VisitPaymentIntegrationService.process_payment_for_existing_visit(
                                db, visit_id, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "visit",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "visit",
                                },
                            )
                    else:
                        # Создаём новую запись на основе платежа
                        success, message, new_appointment_id = (
                            VisitPaymentIntegrationService.create_appointment_from_payment(
                                db, webhook
                            )
                        )
                        if success:
                            logger.info(
                                "payment_webhook_visit_integration_succeeded",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "new_appointment",
                                },
                            )
                        else:
                            logger.warning(
                                "payment_webhook_visit_integration_failed",
                                extra={
                                    "payment_provider": "click",
                                    "webhook_record_id": webhook.id,
                                    "target_type": "new_appointment",
                                },
                            )

                except Exception as exc:
                    logger.error(
                        "payment_webhook_visit_integration_exception",
                        extra={
                            "payment_provider": "click",
                            "webhook_record_id": webhook.id,
                            "exception_type": type(exc).__name__,
                        },
                    )
                    # Не прерываем обработку вебхука из-за ошибки интеграции

            return True, "Webhook processed successfully", webhook

        except Exception as exc:
            logger.error(
                "payment_webhook_processing_exception",
                extra={
                    "payment_provider": "click",
                    "exception_type": type(exc).__name__,
                },
            )
            return False, "Error processing webhook", None

    @staticmethod
    def get_webhook_summary(
        db: Session, provider: str | None = None
    ) -> dict[str, Any]:
        """Получение сводки по вебхукам"""
        try:
            repository = PaymentWebhookProcessingRepository(db)
            total_webhooks = repository.count_webhooks()
            pending_webhooks = len(repository.get_pending_webhooks())
            failed_webhooks = len(repository.get_failed_webhooks())

            total_transactions = repository.count_transactions()
            successful_transactions = len(
                repository.get_transactions_by_status(status="success")
            )
            failed_transactions = len(
                repository.get_transactions_by_status(status="failed")
            )

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
        except Exception as exc:
            logger.error(
                "payment_webhook_summary_exception",
                extra={
                    "provider_filter_set": provider is not None,
                    "exception_type": type(exc).__name__,
                },
            )
            return {"error": "Unable to build webhook summary"}


# Создаём экземпляр сервиса
payment_webhook_service = PaymentWebhookService()
