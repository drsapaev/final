"""
Сервис утренней сборки для присвоения номеров в очередях
Запускается каждое утро для обработки подтвержденных визитов на текущий день
"""

import logging
from datetime import date, datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)

WIZARD_DUPLICATE_ACTIVE_STATUSES = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
)


class MorningAssignmentClaimError(ValueError):
    """Raised when a wizard-family queue claim cannot be resolved safely."""


class MorningAssignmentService:
    """Сервис утренней сборки для присвоения номеров в очередях"""

    def __init__(self, db: Session | None = None):
        self.db: Session | None = db
        self._owns_session = db is None

    def __enter__(self):
        if self.db is None:
            self.db = SessionLocal()
            self._owns_session = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db and self._owns_session:
            self.db.close()

    def ensure_daily_queues_for_all_tags(self, target_date: date) -> int:
        """
        ⭐ PHASE 2: Pre-create DailyQueues for all unique Service.queue_tag values.
        This ensures queues exist BEFORE any registration/editing happens,
        preventing race conditions and silent fallbacks.

        Returns: number of queues created/verified
        """
        # Get all unique non-null queue_tags from active services
        unique_tags = (
            self.db.query(Service.queue_tag)
            .filter(Service.active == True, Service.queue_tag.isnot(None))
            .distinct()
            .all()
        )

        created_count = 0

        # Get default resource doctor for fallback
        default_doctor = (
            self.db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.username == "general_resource", User.is_active == True)
            .first()
        )

        if not default_doctor:
            # Fallback to any active doctor
            default_doctor = self.db.query(Doctor).filter(Doctor.active == True).first()

        if not default_doctor:
            logger.warning("No default doctor found for pre-creating queues")
            return 0

        for (queue_tag,) in unique_tags:
            try:
                # Check if queue already exists for this tag on this day
                existing = (
                    self.db.query(DailyQueue)
                    .filter(
                        DailyQueue.day == target_date,
                        DailyQueue.queue_tag == queue_tag,
                        DailyQueue.active == True
                    )
                    .first()
                )

                if not existing:
                    # Create new DailyQueue for this tag
                    queue_service.get_or_create_daily_queue(
                        self.db,
                        day=target_date,
                        specialist_id=default_doctor.id,
                        queue_tag=queue_tag,
                    )
                    created_count += 1
                    logger.info(f"✅ Pre-created DailyQueue for queue_tag={queue_tag}")

            except Exception as e:
                logger.error(f"Error pre-creating queue for {queue_tag}: {e}")

        if created_count > 0:
            self.db.flush()
            logger.info(f"🏗️ Pre-created {created_count} DailyQueues for {len(unique_tags)} unique queue_tags")

        return created_count

    def run_morning_assignment(
        self, target_date: date | None = None
    ) -> dict[str, any]:
        """
        Основная функция утренней сборки
        Присваивает номера всем подтвержденным визитам на указанную дату
        """
        if not target_date:
            target_date = date.today()

        logger.info(f"🌅 Запуск утренней сборки для {target_date}")

        try:
            # ⭐ PHASE 2: Pre-create DailyQueues for all Service.queue_tag values
            # This prevents silent fallbacks during QR editing and manual registration
            precreated_count = self.ensure_daily_queues_for_all_tags(target_date)
            if precreated_count > 0:
                logger.info(f"🏗️ Pre-created {precreated_count} missing DailyQueues")

            # Получаем все подтвержденные визиты на сегодня без номеров в очередях
            confirmed_visits = self._get_confirmed_visits_without_queues(target_date)

            if not confirmed_visits:
                logger.info(
                    f"✅ Нет подтвержденных визитов без номеров на {target_date}"
                )
                return {
                    "success": True,
                    "message": f"Нет визитов для обработки на {target_date}",
                    "processed_visits": 0,
                    "assigned_visits": 0,
                    "assigned_queues": 0,
                    "total_queue_entries": 0,
                    "errors": [],
                    "date": target_date.isoformat(),
                }

            logger.info(
                f"📋 Найдено {len(confirmed_visits)} подтвержденных визитов для обработки"
            )

            processed_count = 0
            assigned_queues_count = 0
            errors = []

            for visit in confirmed_visits:
                try:
                    queue_assignments = self._assign_queues_for_visit(
                        visit, target_date
                    )
                    if queue_assignments:
                        processed_count += 1
                        assigned_queues_count += len(queue_assignments)

                        # Обновляем статус визита
                        visit.status = "open"  # Готов к приему

                        logger.info(
                            f"✅ Визит {visit.id}: присвоено {len(queue_assignments)} номеров"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Визит {visit.id}: не удалось присвоить номера"
                        )

                except Exception as e:
                    error_msg = f"Ошибка обработки визита {visit.id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Сохраняем изменения
            self.db.commit()

            result = {
                "success": True,
                "message": f"Утренняя сборка завершена для {target_date}",
                "processed_visits": processed_count,
                "assigned_visits": processed_count,
                "assigned_queues": assigned_queues_count,
                "total_queue_entries": assigned_queues_count,
                "errors": errors,
                "date": target_date.isoformat(),
            }

            logger.info(
                f"🎉 Утренняя сборка завершена: {processed_count} визитов, {assigned_queues_count} номеров"
            )
            return result

        except Exception as e:
            self.db.rollback()
            error_msg = f"Критическая ошибка утренней сборки: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "processed_visits": 0,
                "assigned_visits": 0,
                "assigned_queues": 0,
                "total_queue_entries": 0,
                "errors": [error_msg],
                "date": target_date.isoformat(),
            }

    def run_assignment_job(self, target_date: date | None = None) -> dict[str, any]:
        """
        Backward-compatible wrapper used by legacy tests/callers.
        """
        result = self.run_morning_assignment(target_date)
        result.setdefault("assigned_visits", result.get("processed_visits", 0))
        result.setdefault("total_queue_entries", result.get("assigned_queues", 0))
        return result

    def _get_confirmed_visits_without_queues(self, target_date: date) -> list[Visit]:
        """Получает подтвержденные визиты на указанную дату без номеров в очередях"""

        # Находим визиты со статусом "confirmed" на указанную дату
        confirmed_visits = (
            self.db.query(Visit)
            .filter(
                and_(
                    Visit.visit_date == target_date,
                    Visit.status == "confirmed",
                    Visit.confirmed_at.isnot(None),
                )
            )
            .all()
        )

        # Фильтруем визиты, у которых еще нет записей в очередях
        visits_without_queues = []

        for visit in confirmed_visits:
            # Проверяем есть ли уже записи в очередях для этого визита
            existing_queue_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.patient_id == visit.patient_id)
                .join(DailyQueue)
                .filter(DailyQueue.day == target_date)
                .all()
            )

            # Если нет записей в очередях или они не покрывают все услуги визита
            if not existing_queue_entries:
                visits_without_queues.append(visit)
                continue

            # Проверяем покрывают ли существующие записи все queue_tag визита
            visit_queue_tags = self._get_visit_queue_tags(visit)
            existing_queue_tags = set()

            for entry in existing_queue_entries:
                queue = (
                    self.db.query(DailyQueue)
                    .filter(DailyQueue.id == entry.queue_id)
                    .first()
                )
                if queue and queue.queue_tag:
                    existing_queue_tags.add(queue.queue_tag)

            # Если не все queue_tag покрыты, добавляем визит для обработки
            if not visit_queue_tags.issubset(existing_queue_tags):
                visits_without_queues.append(visit)

        return visits_without_queues

    def _get_visit_queue_tags(self, visit: Visit) -> set:
        """Получает все queue_tag для услуг визита"""
        # ✅ ИСПРАВЛЕНО: Явный импорт для избежания проблем с циклическими зависимостями
        from app.models.visit import VisitService

        visit_services = (
            self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        queue_tags = set()
        for vs in visit_services:
            service = self.db.query(Service).filter(Service.id == vs.service_id).first()
            if service and service.queue_tag:
                queue_tags.add(service.queue_tag)

        return queue_tags

    def _assign_queues_for_visit(
        self,
        visit: Visit,
        target_date: date,
        source: str = "morning_assignment",
    ) -> list[dict[str, any]]:
        """Присваивает номера в очередях для конкретного визита"""

        # Получаем уникальные queue_tag из услуг визита
        unique_queue_tags = self._get_visit_queue_tags(visit)

        if not unique_queue_tags:
            logger.warning(f"Визит {visit.id}: нет queue_tag в услугах")
            return []

        queue_assignments = []

        for queue_tag in unique_queue_tags:
            try:
                assignment = self._assign_single_queue(
                    visit,
                    queue_tag,
                    target_date,
                    source=source,
                )
                if assignment:
                    queue_assignments.append(assignment)
            except Exception as e:
                logger.error(
                    f"Ошибка присвоения очереди {queue_tag} для визита {visit.id}: {e}",
                    exc_info=True
                )
                # ✅ SECURITY: Rollback session при ошибке foreign key
                try:
                    self.db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Ошибка при rollback: {rollback_error}")

        return queue_assignments

    def _assign_single_queue(
        self,
        visit: Visit,
        queue_tag: str,
        target_date: date,
        *,
        source: str = "morning_assignment",
    ) -> dict[str, any] | None:
        """Присваивает номер в конкретной очереди"""

        # Определяем врача для очереди
        doctor_id = visit.doctor_id
        doctor = None

        if doctor_id:
            doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
            if not doctor:
                logger.warning(
                    f"Врач с ID {doctor_id} не найден для queue_tag={queue_tag}, visit_id={visit.id}; используем fallback"
                )
                doctor_id = None

        # Для очередей без конкретного врача используем ресурс-врачей
        if not doctor_id:
            # Маппинг queue_tag → resource_username
            resource_mapping = {
                "ecg": "ecg_resource",
                "lab": "lab_resource",
                "stomatology": "stomatology_resource",
                "general": "general_resource",
                "cardiology_common": "general_resource",  # Используем общий ресурс
                "dermatology": "general_resource",  # Используем общий ресурс
                "procedures": "general_resource",  # Используем общий ресурс
            }

            resource_username = resource_mapping.get(
                queue_tag, "general_resource"
            )  # Fallback на general_resource

            # ✅ ИСПРАВЛЕНИЕ: Ищем doctor_id через связь User → Doctor
            resource_user = (
                self.db.query(User)
                .filter(User.username == resource_username, User.is_active == True)
                .first()
            )

            if resource_user:
                # Находим запись врача по user_id
                resource_doctor = (
                    self.db.query(Doctor)
                    .filter(Doctor.user_id == resource_user.id)
                    .first()
                )

                if resource_doctor:
                    doctor_id = resource_doctor.id  # Используем doctor_id, а не user_id
                    doctor = resource_doctor
                    logger.info(
                        f"Для queue_tag={queue_tag} используется ресурс-врач: {resource_username} (Doctor ID: {doctor_id})"
                    )
                else:
                    logger.warning(
                        f"У ресурс-пользователя {resource_username} (User ID: {resource_user.id}) нет записи в таблице doctors"
                    )
            else:
                logger.warning(
                    f"Ресурс-врач {resource_username} не найден для queue_tag={queue_tag}"
                )

        if not doctor_id:
            # Last-resort fallback: reuse already opened queue for this tag/day.
            existing_queue = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.queue_tag == queue_tag,
                    DailyQueue.active == True,
                )
                .first()
            )
            if existing_queue:
                doctor_id = existing_queue.specialist_id
            else:
                logger.warning(
                    f"Не найден врач для queue_tag={queue_tag}, visit_id={visit.id}"
                )
                return None

        logger.info(
            f"Используем doctor_id={doctor_id} для queue_tag={queue_tag}, visit_id={visit.id}"
        )

        defaults = {}
        if doctor:
            defaults = {
                "cabinet_number": doctor.cabinet,
                "max_online_entries": (
                    doctor.max_online_per_day
                    if hasattr(doctor, 'max_online_per_day')
                    else None
                ),
            }

        daily_queue, existing_entry = self._resolve_existing_queue_claim_or_raise(
            patient_id=visit.patient_id,
            target_date=target_date,
            queue_tag=queue_tag,
        )

        if not daily_queue:
            # ✅ ИСПРАВЛЕНО: specialist_id должен быть doctor.id (ForeignKey на doctors.id)
            daily_queue = queue_service.get_or_create_daily_queue(
                self.db,
                day=target_date,
                specialist_id=doctor_id,  # ✅ Используем doctor_id, а не user_id
                queue_tag=queue_tag,
                defaults=defaults,
            )

        if existing_entry:
            logger.info(f"Пациент {visit.patient_id} уже есть в очереди {queue_tag}")
            return {
                "queue_tag": queue_tag,
                "queue_id": daily_queue.id,
                "number": existing_entry.number,
                "status": "existing",
            }

        # ✅ ИСПРАВЛЕНО: Используем SSOT queue_service для создания записи
        # Получаем информацию о пациенте для передачи в create_queue_entry
        patient = self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
        patient_name = None
        phone = None
        if patient:
            # Формируем имя пациента
            if hasattr(patient, 'short_name'):
                patient_name = patient.short_name()
            elif hasattr(patient, 'last_name') and hasattr(patient, 'first_name'):
                patient_name = f"{patient.last_name} {patient.first_name}".strip()
            phone = patient.phone if hasattr(patient, 'phone') else None

        # Получаем queue_time (бизнес-время регистрации)
        from zoneinfo import ZoneInfo

        from app.crud.clinic import get_queue_settings

        queue_settings = get_queue_settings(self.db)
        timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        queue_time = datetime.now(timezone)

        # ⭐ ИСПРАВЛЕНО: Получаем услуги визита для данного queue_tag
        visit_services = (
            self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        # Фильтруем услуги по queue_tag и формируем services/service_codes
        services_for_entry = []
        service_codes_for_entry = []

        for vs in visit_services:
            service = self.db.query(Service).filter(Service.id == vs.service_id).first()
            if service and service.queue_tag == queue_tag:
                # ⭐ Используем service_code если есть, иначе code
                code = service.service_code or service.code
                if code:
                    service_codes_for_entry.append(code.upper() if code else None)
                    services_for_entry.append({
                        "id": service.id,
                        "code": code.upper() if code else None,
                        "name": service.name,
                        "price": float(vs.price) if vs.price else 0,
                    })

        # Если не нашли услуги с matching queue_tag, добавляем все услуги визита
        if not services_for_entry:
            for vs in visit_services:
                service = self.db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    code = service.service_code or service.code
                    if code:
                        service_codes_for_entry.append(code.upper() if code else None)
                        services_for_entry.append({
                            "id": service.id,
                            "code": code.upper() if code else None,
                            "name": service.name,
                            "price": float(vs.price) if vs.price else 0,
                        })

        # ✅ ИСПРАВЛЕНО: Используем SSOT метод для создания записи С услугами
        queue_entry = queue_service.create_queue_entry(
            self.db,
            daily_queue=daily_queue,
            patient_id=visit.patient_id,
            patient_name=patient_name,
            phone=phone,
            visit_id=visit.id,
            source=source,  # Источник: зависит от сценария (desk / morning_assignment / confirmation)
            status="waiting",
            queue_time=queue_time,  # Бизнес-время регистрации
            services=services_for_entry,  # ⭐ ДОБАВЛЕНО: услуги с кодами
            service_codes=service_codes_for_entry,  # ⭐ ДОБАВЛЕНО: коды услуг
            auto_number=True,  # Автоматически присваиваем номер
            commit=False,  # Не коммитим сразу, коммит будет в run_morning_assignment
        )

        logger.info(
            f"Присвоен номер {queue_entry.number} в очереди {queue_tag} для пациента {visit.patient_id} (через SSOT), услуги: {service_codes_for_entry}"
        )

        return {
            "queue_tag": queue_tag,
            "queue_id": daily_queue.id,
            "number": queue_entry.number,
            "status": "assigned",
        }

    def _resolve_existing_queue_claim_or_raise(
        self,
        *,
        patient_id: int,
        target_date: date,
        queue_tag: str,
    ) -> tuple[DailyQueue | None, OnlineQueueEntry | None]:
        active_queues = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date,
                DailyQueue.queue_tag == queue_tag,
                DailyQueue.active == True,
            )
            .order_by(DailyQueue.id.asc())
            .all()
        )

        if not active_queues:
            return None, None

        active_entries = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id.in_([queue.id for queue in active_queues]),
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(WIZARD_DUPLICATE_ACTIVE_STATUSES),
            )
            .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
            .all()
        )

        if len(active_entries) > 1:
            raise MorningAssignmentClaimError(
                "Неоднозначная активная запись очереди для queue_tag="
                f"{queue_tag} и пациента {patient_id}"
            )

        if len(active_entries) == 1:
            queue_by_id = {queue.id: queue for queue in active_queues}
            matched_queue = queue_by_id.get(active_entries[0].queue_id)
            if matched_queue is None:
                raise MorningAssignmentClaimError(
                    "Не удалось безопасно сопоставить активную запись очереди с "
                    f"queue_tag={queue_tag} и пациентом {patient_id}"
                )
            return matched_queue, active_entries[0]

        if len(active_queues) > 1:
            raise MorningAssignmentClaimError(
                "Неоднозначная очередь для queue_tag="
                f"{queue_tag} и пациента {patient_id}"
            )

        return active_queues[0], None

    def get_morning_assignment_stats(
        self, target_date: date | None = None
    ) -> dict[str, any]:
        """Получает статистику утренней сборки"""
        if not target_date:
            target_date = date.today()

        # Подтвержденные визиты на дату
        confirmed_visits = (
            self.db.query(Visit)
            .filter(
                and_(
                    Visit.visit_date == target_date,
                    Visit.status.in_(["confirmed", "open"]),
                    Visit.confirmed_at.isnot(None),
                )
            )
            .count()
        )

        # Визиты со статусом "open" (уже обработанные)
        processed_visits = (
            self.db.query(Visit)
            .filter(and_(Visit.visit_date == target_date, Visit.status == "open"))
            .count()
        )

        # Записи в очередях на дату
        queue_entries = (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue)
            .filter(DailyQueue.day == target_date)
            .count()
        )

        return {
            "date": target_date.isoformat(),
            "confirmed_visits": confirmed_visits,
            "processed_visits": processed_visits,
            "queue_entries": queue_entries,
            "pending_processing": confirmed_visits - processed_visits,
        }


# Глобальная функция для запуска утренней сборки
def run_morning_assignment(target_date: date | None = None) -> dict[str, any]:
    """
    Запускает утреннюю сборку для присвоения номеров в очередях
    Может быть вызвана из cron job или API эндпоинта
    """
    with MorningAssignmentService() as service:
        return service.run_morning_assignment(target_date)


def get_assignment_stats(target_date: date | None = None) -> dict[str, any]:
    """Получает статистику утренней сборки"""
    with MorningAssignmentService() as service:
        return service.get_morning_assignment_stats(target_date)


# Функция для тестирования
def test_morning_assignment():
    """Тестовая функция для проверки утренней сборки"""
    logger.info("🧪 Запуск тестирования утренней сборки")

    result = run_morning_assignment()
    stats = get_assignment_stats()

    logger.info(
        "Результат утренней сборки: Успех=%s, Обработано визитов=%d, Присвоено номеров=%d, Ошибки=%d",
        result['success'],
        result['processed_visits'],
        result['assigned_queues'],
        len(result['errors']),
    )
    logger.info(
        "Статистика: Подтвержденные визиты=%d, Обработанные визиты=%d, Записи в очередях=%d, Ожидают обработки=%d",
        stats['confirmed_visits'],
        stats['processed_visits'],
        stats['queue_entries'],
        stats['pending_processing'],
    )

    return result, stats


if __name__ == "__main__":
    # Запуск тестирования при прямом вызове
    test_morning_assignment()
