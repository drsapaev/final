"""Patients mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from sqlalchemy import text

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


def _normalize_person_name(raw: str | None) -> str:
    """Case- and whitespace-insensitive person-name key (RQ-25.a.1)."""
    return " ".join((raw or "").split()).casefold()


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

        RQ-25.a.1 (ACCEPTANCE S-22): общий телефон — НЕ достаточное
        основание считать двух людей одним пациентом. Идентичность
        = телефон + нормализованное полное имя:
        - ровно одно совпадение (телефон + имя) → переиспользуем карту
          (повторная запись того же человека не плодит дубли);
        - телефон совпадает, имя НЕТ → второй член семьи получает
          СВОЮ карту (раньше молча прикреплялся к чужой записи —
          wrong-patient PHI linkage);
        - несколько карт с тем же телефоном и именем → неоднозначность
          НЕ разрешается выбором первой строки: громкий отказ (400),
          разрешение на стойке; данные существующих карт не трогаем.

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

        # Сериализуем конкурентные join'ы одного телефона на PostgreSQL:
        # без блокировки двойная отправка (два таба/повтор) успевает
        # создать две карты до взаимной видимости — advisory lock делает
        # второго писателя свидетелем карты первого (это сериализация
        # создания, НЕ замена идентичности уникальным индексом).
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"qr_patient:{clean_phone}"},
            )

        wanted_name = _normalize_person_name(patient_name)

        # Ищем кандидатов по телефону (с нормализацией) и уточняем по имени
        candidates = (
            self.db.query(Patient)
            .filter(
                func.replace(func.replace(Patient.phone, '+', ''), ' ', '') == clean_phone
            )
            .all()
        )

        exact_matches = [
            p
            for p in candidates
            if _normalize_person_name(p.full_name) == wanted_name
        ]

        if len(exact_matches) == 1:
            patient = exact_matches[0]
            logger.info(
                "[QRQueueService._find_or_create_patient] ✅ Найден существующий пациент ID=%d",
                patient.id,
            )
            return patient

        if len(exact_matches) > 1:
            # RQ-25.a.1: неоднозначность (несколько карт с тем же телефоном
            # и именем) не разрешается выбором первой строки — громкий
            # отказ, разрешение на стойке.
            logger.warning(
                "[QRQueueService._find_or_create_patient] ⚠️ Неоднозначный пациент по телефону+имени (совпадений: %d)",
                len(exact_matches),
            )
            raise ValueError(
                "По указанному телефону найдено несколько пациентов с таким именем. "
                "Обратитесь в регистратуру для уточнения."
            )

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
