"""Patients mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


class PatientsMixin(QRQueueServiceMixinBase):
    """Patients methods for QRQueueService."""

    def _find_or_create_patient(
        self,
        patient_name: str,
        phone: str,
        birth_year: int | None = None,
        address: str | None = None,
    ) -> Patient:
        """
        ⭐ FIX: Находит или создаёт пациента по телефону.

        SSOT для создания пациентов при QR-регистрации.
        Гарантирует, что patient_id ВСЕГДА будет заполнен.

        Args:
            patient_name: ФИО пациента
            phone: Номер телефона
            birth_year: Год рождения (опционально)
            address: Адрес (опционально)

        Returns:
            Patient instance (существующий или новый)
        """
        # Нормализуем телефон для поиска
        clean_phone = re.sub(r'\D', '', phone or '')

        if not clean_phone:
            logger.warning(
                "[QRQueueService._find_or_create_patient] ⚠️ Пустой телефон, невозможно найти/создать пациента"
            )
            return None

        # Ищем по телефону (с нормализацией)
        patient = (
            self.db.query(Patient)
            .filter(
                func.replace(func.replace(Patient.phone, '+', ''), ' ', '') == clean_phone
            )
            .first()
        )

        if patient:
            logger.info(
                "[QRQueueService._find_or_create_patient] ✅ Найден существующий пациент ID=%d",
                patient.id,
            )
            return patient

        # Создаём нового пациента
        # Парсим ФИО
        name_parts = patient_name.strip().split() if patient_name else []
        last_name = name_parts[0] if len(name_parts) > 0 else "Неизвестный"
        first_name = name_parts[1] if len(name_parts) > 1 else "Пациент"
        middle_name = name_parts[2] if len(name_parts) > 2 else None

        patient = Patient(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            phone=phone,
            birth_date=date(birth_year, 1, 1) if birth_year else None,
            address=address,
        )
        self.db.add(patient)
        self.db.flush()

        logger.info(
            "[QRQueueService._find_or_create_patient] ✅ Создан новый пациент ID=%d для QR-регистрации",
            patient.id,
        )

        return patient


