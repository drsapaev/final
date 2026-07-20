"""Visits mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


class VisitsMixin(QRQueueServiceMixinBase):
    """Visits methods for QRQueueService."""

    def _create_visit_for_qr(
        self,
        patient_id: int,
        visit_date: date,
        services: list[dict[str, Any]],
        visit_type: str = "paid",
        discount_mode: str = "none",
        notes: str | None = None,
    ) -> Visit:
        """
        ⭐ FIX 2: Создаёт Visit для QR-регистрации.

        Вызывается при первом заполнении QR-записи (когда регистратор добавляет услуги).
        Visit создаётся сразу со списком услуг.

        Args:
            patient_id: ID пациента
            visit_date: Дата визита
            services: Список услуг с полными данными (service_id, name, code, price, qty)
            visit_type: Тип визита (paid, repeat, benefit)
            discount_mode: Режим скидки (none, repeat, benefit, all_free)
            notes: Заметки к визиту

        Returns:
            Visit instance
        """
        from decimal import Decimal

        from app.models.visit import Visit, VisitService

        # Создаём Visit
        # ✅ SSOT: source='online' для QR/Telegram регистрации
        visit = Visit(
            patient_id=patient_id,
            visit_date=visit_date,
            status="open",
            discount_mode=discount_mode,
            approval_status="none",
            notes=notes or f"QR-регистрация ({visit_type})",
            source="online",  # ✅ SSOT: Прямое присвоение source
        )
        self.db.add(visit)
        self.db.flush()  # Получаем ID

        # Добавляем услуги к Visit
        for svc_data in services:
            visit_service = VisitService(
                visit_id=visit.id,
                service_id=svc_data.get("service_id"),
                code=svc_data.get("code"),
                name=svc_data.get("name", "Услуга"),
                qty=svc_data.get("quantity", 1),
                price=Decimal(str(svc_data.get("price", 0))) if svc_data.get("price") else None,
            )
            self.db.add(visit_service)

        self.db.flush()

        logger.info(
            "[QRQueueService._create_visit_for_qr] ✅ Создан Visit ID=%d с %d услугами",
            visit.id,
            len(services),
        )

        return visit

    # ============================================================
    # === QR TOKEN MANAGEMENT ===
    # ============================================================


