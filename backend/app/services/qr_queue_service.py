"""
Сервис для управления QR очередями
"""

import base64
import io
import logging
import secrets
import socket
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import qrcode
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.models.clinic import Doctor
from app.models.online_queue import (
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueStatistics,
    QueueToken,
)
from app.models.patient import Patient
from app.models.user import User
from app.services.feature_flags import is_feature_enabled
from app.services.queue_service import (
    queue_service,
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
)


class QRQueueService:
    """Сервис для управления QR очередями"""

    def __init__(self, db: Session):
        self.db = db

    def generate_qr_token(
        self,
        specialist_id: int,
        department: str,
        generated_by_user_id: int,
        expires_hours: int = 24,
        target_date: Optional[str] = None,
        visit_type: str = "paid",
    ) -> Dict[str, Any]:
        """
        Генерирует QR токен для присоединения к очереди

        Args:
            specialist_id: ID специалиста
            department: Отделение
            generated_by_user_id: ID пользователя, создавшего токен
            expires_hours: Время жизни токена в часах
            target_date: Целевая дата (YYYY-MM-DD), если None - автоматически
            visit_type: Тип визита (paid, repeat, benefit)

        Returns:
            Словарь с данными токена и QR кодом
        """
        # ✅ Определяем target_date: либо из параметра, либо автоматически
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today = date.today()

        if target_date:
            # Если дата передана явно, используем ее
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            logger.debug(
                f"[QRQueueService] Используется явно указанная дата: {target_date}"
            )
        else:
            # Если после 09:00 - создаем на завтра, иначе на сегодня
            if current_time > "09:00":
                target_date = today + timedelta(days=1)
                logger.debug(
                    f"[QRQueueService] Текущее время {current_time} > 09:00, создаем QR на завтра: {target_date}"
                )
            else:
                target_date = today
                logger.debug(
                    f"[QRQueueService] Текущее время {current_time} <= 09:00, создаем QR на сегодня: {target_date}"
                )

        token, token_meta = queue_service.assign_queue_token(
            self.db,
            specialist_id=specialist_id,
            department=department,
            generated_by_user_id=generated_by_user_id,
            target_date=target_date,
            expires_hours=expires_hours,
            is_clinic_wide=False,
        )

        # ✅ ДИНАМИЧЕСКИЙ URL: Получаем актуальный IP адрес
        base_url = self._get_frontend_url()
        qr_url = f"/queue/join?token={token}"
        full_qr_url = f"{base_url}{qr_url}"

        logger.debug(f"[QRQueueService] QR URL: {full_qr_url}")

        qr_code_data = self._generate_qr_code(full_qr_url)

        return {
            "token": token,
            "qr_url": qr_url,  # Относительный URL для фронтенда
            "qr_code_base64": qr_code_data,
            "specialist_id": specialist_id,
            "department": department,
            "expires_at": (
                token_meta["expires_at"].isoformat()
                if token_meta.get("expires_at")
                else None
            ),
            "active": True,
        }

    def get_qr_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о QR токене

        Args:
            token: QR токен

        Returns:
            Информация о токене или None если не найден
        """
        try:
            from zoneinfo import ZoneInfo

            from app.crud import clinic as crud_clinic

            logger.debug(
                f"[QRQueueService.get_qr_token_info] Запрос информации о токене: {token[:20]}..."
            )

            # Получаем timezone для правильного сравнения
            queue_settings = crud_clinic.get_queue_settings(self.db)
            timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
            now = datetime.now(timezone)

            logger.debug(
                f"[QRQueueService.get_qr_token_info] Текущее время (timezone-aware): {now}"
            )

            # Сначала проверим, существует ли токен вообще
            qr_token_any = (
                self.db.query(QueueToken).filter(QueueToken.token == token).first()
            )

            if qr_token_any:
                logger.debug(f"[QRQueueService.get_qr_token_info] Токен найден в БД:")
                logger.debug(f"  - active: {qr_token_any.active}")
                logger.debug(f"  - expires_at: {qr_token_any.expires_at}")
                logger.debug(f"  - specialist_id: {qr_token_any.specialist_id}")
                logger.debug(f"  - is_clinic_wide: {qr_token_any.is_clinic_wide}")
                if qr_token_any.expires_at:
                    # Сравниваем timezone-aware datetime
                    expires_aware = (
                        qr_token_any.expires_at
                        if qr_token_any.expires_at.tzinfo
                        else qr_token_any.expires_at.replace(tzinfo=timezone)
                    )
                    logger.debug(f"  - истек: {expires_aware <= now}")
            else:
                logger.debug(
                    f"[QRQueueService.get_qr_token_info] Токен вообще не найден в БД!"
                )

            # Используем timezone-aware datetime для сравнения
            qr_token = (
                self.db.query(QueueToken)
                .filter(QueueToken.token == token, QueueToken.active == True)
                .first()
            )

            if not qr_token:
                logger.debug(
                    f"[QRQueueService.get_qr_token_info] Токен не найден или неактивен"
                )
                return None

            # Проверяем срок действия с учетом timezone
            # SQLite сохраняет datetime без timezone в локальном времени
            # expires_at сохранен как naive datetime в локальном времени (Asia/Tashkent)
            if qr_token.expires_at:
                # expires_at - это naive datetime в локальном времени
                # now - это timezone-aware datetime в локальном времени
                # Конвертируем expires_at в timezone-aware для сравнения
                expires_aware = qr_token.expires_at.replace(tzinfo=timezone)

                if expires_aware <= now:
                    logger.debug(
                        f"[QRQueueService.get_qr_token_info] Токен истек: {expires_aware} <= {now}"
                    )
                    return None
                else:
                    logger.debug(
                        f"[QRQueueService.get_qr_token_info] Токен действителен: {expires_aware} > {now}"
                    )

            logger.debug(
                f"[QRQueueService.get_qr_token_info] Токен найден: specialist_id={qr_token.specialist_id}, is_clinic_wide={qr_token.is_clinic_wide}"
            )

            # ✅ Для общего QR токена (specialist_id = None) не ищем специалиста
            specialist = None
            daily_queue = None

            if qr_token.specialist_id is not None:
                # Получаем информацию о специалисте (только если не общий QR)
                specialist = (
                    self.db.query(Doctor)
                    .filter(Doctor.id == qr_token.specialist_id)
                    .first()
                )

                if not specialist:
                    logger.debug(
                        f"[QRQueueService.get_qr_token_info] ПРЕДУПРЕЖДЕНИЕ: Врач с ID {qr_token.specialist_id} не найден!"
                    )

                # ✅ ИСПРАВЛЕНИЕ: Используем дату из токена, а не today
                target_date = qr_token.day
                logger.debug(
                    f"[QRQueueService.get_qr_token_info] Целевая дата: {target_date}"
                )

                daily_queue = (
                    self.db.query(DailyQueue)
                    .filter(
                        DailyQueue.day == target_date,
                        DailyQueue.specialist_id == qr_token.specialist_id,
                        DailyQueue.active == True,
                    )
                    .first()
                )

            logger.debug(
                f"[QRQueueService.get_qr_token_info] DailyQueue найдена: {daily_queue is not None}"
            )
        except Exception as e:
            logger.error(
                f"[QRQueueService.get_qr_token_info] КРИТИЧЕСКАЯ ОШИБКА в начальной части: {e}"
            )
            import traceback

            traceback.print_exc()
            return None

        # ✅ ИСПРАВЛЕНИЕ: Правильное получение имени врача и специальности
        # Для общего QR используем специальные значения
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            specialist_name = "Все специалисты"
            specialty_label = "clinic"
            department_name = "Клиника"
            queue_length = 0
        else:
            specialist_name = "Неизвестный специалист"
            specialty_label = qr_token.department or "general"
            department_name = specialty_label
            queue_length = 0

        # Маппинг специальностей на русские названия
        specialty_mapping = {
            'cardiology': 'Кардиолог',
            'cardio': 'Кардиолог',
            'dermatology': 'Дерматолог-косметолог',
            'derma': 'Дерматолог-косметолог',
            'stomatology': 'Стоматолог',
            'dentist': 'Стоматолог',
            'dentistry': 'Стоматолог',
            'laboratory': 'Лаборатория',
            'lab': 'Лаборатория',
            'general': 'Общая практика',
            'clinic': 'Клиника',
        }

        try:
            if qr_token.is_clinic_wide or qr_token.specialist_id is None:
                # Общий QR - не нужен специалист
                specialist_name = "Все специалисты"
                department_name = "Клиника"
                specialty_label = "clinic"
            elif specialist:
                # Получаем имя врача из связанного User
                try:
                    if hasattr(specialist, 'user') and specialist.user:
                        specialist_name = (
                            specialist.user.full_name
                            or f"Врач ID {qr_token.specialist_id}"
                        )
                    elif hasattr(specialist, 'user_id') and specialist.user_id:
                        # Пытаемся загрузить user явно
                        user = (
                            self.db.query(User)
                            .filter(User.id == specialist.user_id)
                            .first()
                        )
                        if user and user.full_name:
                            specialist_name = user.full_name
                        else:
                            specialist_name = f"Врач ID {qr_token.specialist_id}"
                    else:
                        specialist_name = f"Врач ID {qr_token.specialist_id}"

                    # ✅ КРИТИЧЕСКИ ВАЖНО: specialist_name никогда не должен быть None или пустым
                    if not specialist_name or (
                        isinstance(specialist_name, str)
                        and specialist_name.strip() == ""
                    ):
                        specialist_name = f"Врач ID {qr_token.specialist_id}"

                    logger.debug(
                        f"[QRQueueService] Имя врача получено: {specialist_name}"
                    )
                except Exception as e:
                    logger.debug(f"[QRQueueService] Ошибка получения имени врача: {e}")
                    specialist_name = f"Врач ID {qr_token.specialist_id}"

                # Используем специальность врача из базы, если есть
                try:
                    if hasattr(specialist, 'specialty') and specialist.specialty:
                        specialty_label = specialty_mapping.get(
                            specialist.specialty, specialist.specialty
                        )
                    else:
                        # Если нет специальности у врача, используем department из токена
                        specialty_label = specialty_mapping.get(
                            qr_token.department,
                            self._get_department_name(qr_token.department),
                        )
                except Exception as e:
                    logger.debug(
                        f"[QRQueueService] Ошибка получения специальности: {e}"
                    )
                    specialty_label = specialty_mapping.get(
                        qr_token.department,
                        self._get_department_name(qr_token.department),
                    )

                # ✅ Подсчитываем текущую длину очереди из реальных записей (Visit + Appointment)
                try:
                    from app.models.appointment import Appointment
                    from app.models.visit import Visit

                    # Используем target_date из токена
                    target_date = qr_token.day

                    # Считаем Visit записи на target_date для этого врача
                    visit_count = (
                        self.db.query(Visit)
                        .filter(
                            Visit.visit_date == target_date,
                            Visit.doctor_id == specialist.id,
                        )
                        .count()
                    )

                    # ✅ Защита от None
                    if visit_count is None:
                        visit_count = 0
                    logger.debug(f"[QRQueueService] visit_count: {visit_count}")

                    # Считаем Appointment записи на target_date для этого врача
                    appointment_count = (
                        self.db.query(Appointment)
                        .filter(
                            Appointment.appointment_date == target_date,
                            Appointment.doctor_id == specialist.id,
                        )
                        .count()
                    )

                    # ✅ Защита от None
                    if appointment_count is None:
                        appointment_count = 0
                    logger.debug(
                        f"[QRQueueService] appointment_count: {appointment_count}"
                    )

                    queue_length = visit_count + appointment_count
                    logger.debug(f"[QRQueueService] queue_length: {queue_length}")
                except Exception as e:
                    logger.debug(f"[QRQueueService] Ошибка подсчета очереди: {e}")
                    import traceback

                    traceback.print_exc()
                    queue_length = 0
        except Exception as e:
            logger.error(
                f"[QRQueueService] Критическая ошибка обработки специалиста: {e}"
            )
            import traceback

            traceback.print_exc()
            specialty_label = specialty_mapping.get(
                qr_token.department, self._get_department_name(qr_token.department)
            )

        try:
            logger.debug(f"[QRQueueService.get_qr_token_info] Формируем ответ...")

            # ✅ ФИНАЛЬНАЯ ПРОВЕРКА: Гарантируем что specialist_name не None
            if specialist_name is None or specialist_name == "":
                if qr_token.is_clinic_wide or qr_token.specialist_id is None:
                    specialist_name = "Все специалисты"
                else:
                    specialist_name = f"Врач ID {qr_token.specialist_id}"

            # Определяем target_date из токена
            target_date = qr_token.day

            # Для общего QR queue_active всегда True (если токен активен)
            queue_active = True
            if not qr_token.is_clinic_wide and qr_token.specialist_id is not None:
                queue_active = (
                    daily_queue is not None and daily_queue.active
                    if daily_queue
                    else False
                )

            # Определяем department_name
            final_department_name = (
                department_name
                if qr_token.is_clinic_wide or qr_token.specialist_id is None
                else specialty_mapping.get(specialty_label, specialty_label)
            )

            # Форматируем expires_at (может быть naive datetime из SQLite)
            expires_at_str = None
            if qr_token.expires_at:
                # Если naive datetime, добавляем timezone для правильного форматирования
                if qr_token.expires_at.tzinfo is None:
                    expires_aware = qr_token.expires_at.replace(tzinfo=timezone)
                else:
                    expires_aware = qr_token.expires_at
                expires_at_str = expires_aware.isoformat()

            result = {
                "token": token,
                "specialist_id": qr_token.specialist_id,
                "specialist_name": specialist_name,
                "department": qr_token.department or "clinic",
                "department_name": final_department_name,
                "queue_length": queue_length,
                "queue_active": queue_active,
                "expires_at": expires_at_str,
                "is_clinic_wide": qr_token.is_clinic_wide
                or qr_token.specialist_id is None,
                "target_date": target_date.isoformat() if target_date else None,
            }
            logger.debug(
                f"[QRQueueService.get_qr_token_info] Ответ сформирован успешно: {result}"
            )
            return result
        except Exception as e:
            logger.error(
                f"[QRQueueService.get_qr_token_info] ОШИБКА при формировании ответа: {e}"
            )
            import traceback

            traceback.print_exc()
            return None

    def start_join_session(
        self, token: str, ip_address: str = None, user_agent: str = None
    ) -> Dict[str, Any]:
        """
        Начинает сессию присоединения к очереди

        Args:
            token: QR токен
            ip_address: IP адрес пользователя
            user_agent: User-Agent пользователя

        Returns:
            Данные сессии
        """
        logger.debug(
            f"[QRQueueService.start_join_session] Начало сессии для токена: {token[:20]}..."
        )

        try:
            # Проверяем токен
            token_info = self.get_qr_token_info(token)
            if not token_info:
                error_msg = "Недействительный или истекший QR токен"
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            logger.debug(
                f"[QRQueueService.start_join_session] Токен найден: queue_active={token_info.get('queue_active')}"
            )

            # Для общего QR токена разрешаем создание сессии даже если queue_active=False
            # (так как очереди могут быть еще не созданы)
            if not token_info.get("is_clinic_wide") and not token_info.get(
                "queue_active", False
            ):
                error_msg = "Очередь в данный момент не активна"
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            # Проверяем временные ограничения
            logger.debug(
                f"[QRQueueService.start_join_session] Проверка временных ограничений..."
            )
            time_check = self._check_online_time_restrictions(token)
            logger.debug(
                f"[QRQueueService.start_join_session] Результат проверки времени: allowed={time_check.get('allowed')}, message={time_check.get('message')}"
            )

            if not time_check.get("allowed", False):
                error_msg = time_check.get(
                    "message", "Временные ограничения не пройдены"
                )
                logger.debug(f"[QRQueueService.start_join_session] ❌ {error_msg}")
                raise ValueError(error_msg)

            # Генерируем токен сессии
            session_token = secrets.token_urlsafe(32)

            # Создаем сессию
            session = QueueJoinSession(
                session_token=session_token,
                qr_token=token,
                patient_name="",  # Будет заполнено пользователем
                phone="",  # Будет заполнено пользователем
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=datetime.utcnow()
                + timedelta(minutes=15),  # 15 минут на заполнение
            )

            self.db.add(session)
            self.db.commit()

            # Добавляем информацию о времени в ответ
            token_info.update(time_check)

            return {
                "session_token": session_token,
                "expires_at": session.expires_at.isoformat(),
                "queue_info": token_info,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"[QRQueueService.start_join_session] КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback

            traceback.print_exc()
            raise ValueError(f"Ошибка сервера при создании сессии: {str(e)}")

    def complete_join_session(
        self,
        session_token: str,
        patient_name: str,
        phone: str,
        telegram_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Завершает сессию присоединения к очереди

        Args:
            session_token: Токен сессии
            patient_name: ФИО пациента
            phone: Телефон пациента
            telegram_id: Telegram ID (опционально)

        Returns:
            Результат присоединения к очереди
        """
        # Находим сессию
        # expires_at сохраняется в UTC (datetime.utcnow()), поэтому сравниваем с UTC
        now_utc = datetime.utcnow()

        session = (
            self.db.query(QueueJoinSession)
            .filter(
                QueueJoinSession.session_token == session_token,
                QueueJoinSession.status == "pending",
                QueueJoinSession.expires_at > now_utc,
            )
            .first()
        )

        if not session:
            raise ValueError("Сессия не найдена или истекла")

        # Получаем информацию о токене
        qr_token = (
            self.db.query(QueueToken)
            .filter(QueueToken.token == session.qr_token)
            .first()
        )

        if not qr_token:
            raise ValueError("QR токен не найден")

        patient = self.db.query(Patient).filter(Patient.phone == phone).first()

        try:
            join_result = queue_service.join_queue_with_token(
                self.db,
                token_str=qr_token.token,
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id,
                patient_id=patient.id if patient else None,
                source="online",
            )
        except (QueueValidationError, QueueConflictError, QueueNotFoundError) as exc:
            raise ValueError(str(exc)) from exc

        queue_entry = join_result["entry"]
        queue_length_before = join_result["queue_length_before"]
        estimated_wait = join_result["estimated_wait_minutes"]

        # Обновляем сессию
        session.status = "joined"
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = queue_entry.id
        session.queue_number = queue_entry.number
        session.joined_at = datetime.utcnow()

        self.db.commit()

        if not join_result["duplicate"]:
            self._update_queue_statistics(queue_entry.queue_id, "online_joins")

        # ✅ Получаем имя врача правильно (из User)
        specialist_name = join_result.get("specialist_name")
        if not specialist_name:
            specialist_name = f"Врач ID {qr_token.specialist_id}"

        return {
            "success": True,
            "queue_number": queue_entry.number,
            "queue_length": queue_length_before,  # ✅ Используем сохраненное значение ДО добавления
            "estimated_wait_time": estimated_wait,
            "specialist_name": specialist_name,
            "department": qr_token.department,
        }

    def complete_join_session_multiple(
        self,
        session_token: str,
        specialist_ids: List[int],
        patient_name: str,
        phone: str,
        telegram_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Завершает сессию присоединения для нескольких специалистов (общий QR).
        """
        if not specialist_ids:
            raise ValueError("Не выбраны специалисты для записи")

        # expires_at сохраняется в UTC (datetime.utcnow()), поэтому сравниваем с UTC
        now_utc = datetime.utcnow()

        session = (
            self.db.query(QueueJoinSession)
            .filter(
                QueueJoinSession.session_token == session_token,
                QueueJoinSession.status == "pending",
                QueueJoinSession.expires_at > now_utc,
            )
            .first()
        )

        if not session:
            raise ValueError("Сессия не найдена или истекла")

        qr_token = (
            self.db.query(QueueToken)
            .filter(QueueToken.token == session.qr_token)
            .first()
        )
        if not qr_token:
            raise ValueError("QR токен не найден")

        patient = self.db.query(Patient).filter(Patient.phone == phone).first()

        entries: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for specialist_id in specialist_ids:
            try:
                join_result = queue_service.join_queue_with_token(
                    self.db,
                    token_str=qr_token.token,
                    patient_name=patient_name,
                    phone=phone,
                    telegram_id=telegram_id,
                    patient_id=patient.id if patient else None,
                    specialist_id_override=specialist_id,
                    source="online",
                )
                entry = join_result["entry"]
                entries.append(
                    {
                        "specialist_id": specialist_id,
                        "queue_entry_id": entry.id,
                        "queue_number": entry.number,
                        "duplicate": join_result["duplicate"],
                        "queue_length": join_result["queue_length_before"],
                        "estimated_wait_time": join_result["estimated_wait_minutes"],
                        "specialist_name": join_result.get("specialist_name"),
                        "department": qr_token.department,
                    }
                )
                if not join_result["duplicate"]:
                    self._update_queue_statistics(entry.queue_id, "online_joins")
            except (
                QueueValidationError,
                QueueConflictError,
                QueueNotFoundError,
            ) as exc:
                errors.append(
                    {
                        "specialist_id": specialist_id,
                        "error": str(exc),
                    }
                )

        session.status = "joined"
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = entries[0]["queue_entry_id"] if entries else None
        session.queue_number = entries[0]["queue_number"] if entries else None
        session.joined_at = datetime.utcnow()
        self.db.commit()

        return {
            "success": len(entries) > 0,
            "queue_time": datetime.utcnow().isoformat(),
            "entries": entries,
            "errors": errors or None,
            "message": f"Создано {len(entries)} записей, ошибок: {len(errors)}",
        }

    def get_queue_status(
        self, specialist_id: int, target_date: date = None
    ) -> Dict[str, Any]:
        """
        Получает статус очереди специалиста

        Args:
            specialist_id: ID специалиста
            target_date: Дата (по умолчанию сегодня)

        Returns:
            Статус очереди
        """
        if target_date is None:
            target_date = date.today()

        daily_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == target_date, DailyQueue.specialist_id == specialist_id
            )
            .first()
        )

        if not daily_queue:
            return {
                "active": False,
                "queue_length": 0,
                "current_number": None,
                "entries": [],
            }

        # Получаем записи в очереди
        entries = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == daily_queue.id)
            .order_by(OnlineQueueEntry.number)
            .all()
        )

        # Находим текущий номер (последний вызванный или обслуженный)
        current_number = None
        last_served = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status.in_(["called", "served"]),
            )
            .order_by(OnlineQueueEntry.number.desc())
            .first()
        )

        if last_served:
            current_number = last_served.number

        return {
            "active": daily_queue.active,
            "queue_length": len(
                [e for e in entries if e.status in ["waiting", "called"]]
            ),
            "current_number": current_number,
            "entries": [
                {
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                }
                for entry in entries
            ],
        }

    def call_next_patient(
        self,
        specialist_id: int,
        called_by_user_id: int,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Вызывает следующего пациента в очереди

        Args:
            specialist_id: ID специалиста
            called_by_user_id: ID пользователя, вызвавшего пациента
            target_date: Дата очереди (по умолчанию сегодня)

        Returns:
            Информация о вызванном пациенте
        """
        queue_date = target_date if target_date else date.today()
        daily_queue = (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == queue_date,
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.active == True,
            )
            .first()
        )

        if not daily_queue:
            raise ValueError(f"Очередь не активна на дату {queue_date}")

        # Находим следующего пациента в статусе "waiting"
        next_patient = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(OnlineQueueEntry.number)
            .first()
        )

        if not next_patient:
            return {"success": False, "message": "Нет пациентов в очереди"}

        # Обновляем статус
        next_patient.status = "called"
        next_patient.called_at = datetime.utcnow()
        next_patient.called_by_user_id = called_by_user_id

        self.db.commit()

        return {
            "success": True,
            "patient": {
                "number": next_patient.number,
                "name": next_patient.patient_name,
                "phone": next_patient.phone,
                "source": next_patient.source,
            },
            "queue_length": self._get_queue_length(daily_queue.id),
        }

    def get_active_qr_tokens(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает активные QR токены пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Список активных токенов
        """
        # SQLite возвращает naive datetime в локальном времени
        # Сравниваем с текущим временем в локальном timezone
        from zoneinfo import ZoneInfo

        from app.crud import clinic as crud_clinic

        queue_settings = crud_clinic.get_queue_settings(self.db)
        local_tz = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        now_local = datetime.now(local_tz).replace(tzinfo=None)

        tokens = (
            self.db.query(QueueToken)
            .filter(
                QueueToken.generated_by_user_id == user_id,
                QueueToken.active == True,
                QueueToken.expires_at > now_local,
            )
            .order_by(QueueToken.created_at.desc())
            .all()
        )

        result = []
        for token in tokens:
            # Получаем статистику использования
            sessions_count = (
                self.db.query(QueueJoinSession)
                .filter(QueueJoinSession.qr_token == token.token)
                .count()
            )

            successful_joins = (
                self.db.query(QueueJoinSession)
                .filter(
                    QueueJoinSession.qr_token == token.token,
                    QueueJoinSession.status == "joined",
                )
                .count()
            )

            result.append(
                {
                    "token": token.token,
                    "specialist_id": token.specialist_id,
                    "department": token.department,
                    "created_at": token.created_at.isoformat(),
                    "expires_at": token.expires_at.isoformat(),
                    "sessions_count": sessions_count,
                    "successful_joins": successful_joins,
                    "qr_url": f"https://clinic.example.com/queue/join/{token.token}",
                }
            )

        return result

    def deactivate_qr_token(self, token: str, user_id: int) -> bool:
        """
        Деактивирует QR токен

        Args:
            token: QR токен
            user_id: ID пользователя (должен быть создателем токена)

        Returns:
            True если токен деактивирован
        """
        qr_token = (
            self.db.query(QueueToken)
            .filter(
                QueueToken.token == token,
                QueueToken.generated_by_user_id == user_id,
                QueueToken.active == True,
            )
            .first()
        )

        if not qr_token:
            return False

        qr_token.active = False
        self.db.commit()

        return True

    def _get_frontend_url(self) -> str:
        """
        Определяет URL фронтенда для QR кодов

        Приоритет:
        1. FRONTEND_URL из настроек (если задан явно и не localhost)
        2. Автоматическое определение локального IP (для локальной сети)

        Returns:
            URL вида http://{domain_or_ip}:5173 или https://{domain}
        """
        # Сначала проверяем настройку FRONTEND_URL
        configured_url = settings.FRONTEND_URL

        # Если URL задан явно и это не localhost/127.0.0.1 - используем его
        # Это позволяет задать публичный домен/IP для доступа через интернет
        if configured_url and configured_url not in [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://192.168.1.9:5173",  # Старое значение по умолчанию
        ]:
            logger.debug(
                f"[QRQueueService] Используется FRONTEND_URL из настроек: {configured_url}"
            )
            return configured_url

        # Если не задан явно или это localhost - определяем локальный IP автоматически
        # Это для работы в локальной сети (WiFi)
        try:
            # Создаем временный сокет для определения локального IP
            # Используем подключение к Google DNS (8.8.8.8), но не отправляем данные
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # Подключаемся к внешнему адресу (не отправляем данные)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
            finally:
                s.close()

            frontend_url = f"http://{local_ip}:5173"
            logger.debug(
                f"[QRQueueService] Автоматически определен локальный IP: {frontend_url}"
            )
            return frontend_url
        except Exception as e:
            # Если не удалось определить IP, используем fallback из настроек
            logger.debug(
                f"[QRQueueService] Ошибка определения IP: {e}, используем FRONTEND_URL из настроек: {configured_url}"
            )
            return configured_url or "http://localhost:5173"

    def _generate_qr_code(self, url: str) -> str:
        """Генерирует QR код и возвращает его в base64"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    def _get_queue_length(self, queue_id: int) -> int:
        """Получает текущую длину очереди (все типы записей)"""
        try:
            # Получаем информацию о очереди
            daily_queue = (
                self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
            )

            if not daily_queue:
                return 0

            # Получаем дату очереди
            target_date = daily_queue.day
            specialist_id = daily_queue.specialist_id

            # Считаем все типы записей:
            # 1. Visit (визиты через регистратора)
            # 2. Appointment (предварительные записи)
            # 3. OnlineQueueEntry (онлайн записи через QR)
            from app.models.appointment import Appointment
            from app.models.visit import Visit

            visit_count = (
                self.db.query(Visit)
                .filter(
                    Visit.visit_date == target_date, Visit.doctor_id == specialist_id
                )
                .count()
            )
            if visit_count is None:
                visit_count = 0

            appointment_count = (
                self.db.query(Appointment)
                .filter(
                    Appointment.appointment_date == target_date,
                    Appointment.doctor_id == specialist_id,
                )
                .count()
            )
            if appointment_count is None:
                appointment_count = 0

            # Считаем онлайн записи в этой очереди (только waiting/called)
            online_count = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )
            if online_count is None:
                online_count = 0

            total = visit_count + appointment_count + online_count
            logger.debug(
                f"[_get_queue_length] queue_id={queue_id}, date={target_date}, specialist={specialist_id}"
            )
            logger.debug(
                f"[_get_queue_length] visit={visit_count}, appointment={appointment_count}, online={online_count}, total={total}"
            )

            return total
        except Exception as e:
            logger.error(f"[_get_queue_length] Ошибка: {e}")
            import traceback

            traceback.print_exc()
            return 0

    def _estimate_wait_time(self, queue_id: int, queue_number: int) -> int:
        """Оценивает время ожидания в минутах"""
        try:
            # Получаем реальную длину очереди (сколько всего людей)
            total_queue_length = self._get_queue_length(queue_id)

            # Количество людей впереди = общая длина очереди (до присоединения текущего)
            # Если очередь была пустая (0), то впереди никого
            waiting_before = total_queue_length

            logger.debug(
                f"[_estimate_wait_time] queue_number={queue_number}, total_queue={total_queue_length}, waiting_before={waiting_before}"
            )

            # ✅ Защита от None
            if waiting_before is None:
                waiting_before = 0

            # Простая оценка: 15 минут на пациента
            return waiting_before * 15
        except Exception as e:
            logger.error(f"[_estimate_wait_time] Ошибка: {e}")
            import traceback

            traceback.print_exc()
            return 0

    def _get_department_name(self, department: str) -> str:
        """Получает человекочитаемое название отделения"""
        department_names = {
            "cardiology": "Кардиология",
            "dermatology": "Дерматология",
            "dentistry": "Стоматология",
            "laboratory": "Лаборатория",
            "ecg": "ЭКГ",
            "general": "Общая практика",
        }
        return department_names.get(department, department.title())

    def _update_queue_statistics(self, queue_id: int, stat_field: str):
        """Обновляет статистику очереди"""
        today = date.today()

        stats = (
            self.db.query(QueueStatistics)
            .filter(QueueStatistics.queue_id == queue_id, QueueStatistics.date == today)
            .first()
        )

        if not stats:
            stats = QueueStatistics(queue_id=queue_id, date=today)
            self.db.add(stats)

        # Увеличиваем счетчик
        current_value = getattr(stats, stat_field, 0)
        # ✅ Защита от None
        if current_value is None:
            current_value = 0
        logger.debug(
            f"[_update_queue_statistics] field={stat_field}, current={current_value}, new={current_value + 1}"
        )
        setattr(stats, stat_field, current_value + 1)

        self.db.commit()

    def _check_online_time_restrictions(self, token: str) -> Dict[str, Any]:
        """
        Проверяет временные ограничения для онлайн записи

        Args:
            token: QR токен

        Returns:
            Словарь с результатом проверки
        """
        # Получаем токен
        qr_token = self.db.query(QueueToken).filter(QueueToken.token == token).first()
        if not qr_token:
            return {"allowed": False, "message": "Токен не найден"}

        # ✅ ИСПРАВЛЕНИЕ: Используем дату из токена, а не сегодняшнюю
        target_date = qr_token.day

        logger.debug(f"[_check_online_time_restrictions] Ищем DailyQueue:")
        logger.debug(f"  target_date: {target_date}")
        logger.debug(f"  specialist_id: {qr_token.specialist_id}")
        logger.debug(f"  is_clinic_wide: {qr_token.is_clinic_wide}")

        # ✅ ИСПРАВЛЕНИЕ: Для общего QR ищем любую активную очередь на эту дату
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            # Для общего QR проверяем, что есть хотя бы одна активная очередь
            daily_queue = (
                self.db.query(DailyQueue)
                .filter(DailyQueue.day == target_date, DailyQueue.active == True)
                .first()
            )

            # ✅ ИСПРАВЛЕНИЕ: Для общего QR разрешаем запись даже если очередей еще нет
            # (они могут быть созданы позже, или запись может быть на будущую дату)
            if not daily_queue:
                # Проверяем, что дата не в прошлом
                today = date.today()
                if target_date < today:
                    logger.debug(
                        f"[_check_online_time_restrictions] ❌ Дата {target_date} в прошлом"
                    )
                    return {
                        "allowed": False,
                        "message": f"Нельзя записаться на прошедшую дату ({target_date.strftime('%d.%m.%Y')})",
                    }

                # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем время для сегодняшнего дня
                # Используем ту же логику, что и в check_queue_time_window
                if target_date == today:
                    from app.services.queue_service import QueueBusinessService

                    now = datetime.now()
                    current_time = now.time()
                    start_time = QueueBusinessService.ONLINE_QUEUE_START_TIME  # 07:00

                    if current_time < start_time:
                        logger.debug(
                            f"[_check_online_time_restrictions] ❌ Время еще не наступило: {current_time.strftime('%H:%M')} < {start_time.strftime('%H:%M')}"
                        )
                        return {
                            "allowed": False,
                            "message": f"⏰ Онлайн-запись откроется в {start_time.strftime('%H:%M')}. Текущее время: {current_time.strftime('%H:%M')}",
                            "status": "before_start_time",
                            "start_time": start_time.strftime('%H:%M'),
                            "current_time": current_time.strftime('%H:%M'),
                        }

                # Если дата сегодня (и время прошло) или в будущем, разрешаем запись
                # (очереди могут быть созданы позже или запись может быть на будущую дату)
                logger.debug(
                    f"[_check_online_time_restrictions] ⚠️ Нет активных очередей на {target_date}, но дата валидна - разрешаем запись"
                )
                return {
                    "allowed": True,
                    "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                    "status": "available",
                    "start_time": "07:00",  # Значения по умолчанию
                    "end_time": "09:00",
                    "max_entries": 15,
                    "current_entries": 0,
                    "remaining_slots": 15,
                    "target_date": target_date.isoformat(),
                    "warning": "Очереди еще не созданы, но запись разрешена",
                }

            # Проверяем, что хотя бы одна очередь не открыта
            any_opened = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.active == True,
                    DailyQueue.opened_at.isnot(None),
                )
                .first()
            )

            if any_opened:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                }
        else:
            # Для конкретного специалиста ищем его очередь
            daily_queue = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == target_date,
                    DailyQueue.specialist_id == qr_token.specialist_id,
                    DailyQueue.active == True,
                )
                .first()
            )

            logger.debug(f"  daily_queue найдена: {daily_queue is not None}")
            if daily_queue:
                logger.debug(f"  daily_queue.id: {daily_queue.id}")
                logger.debug(f"  daily_queue.active: {daily_queue.active}")
                logger.debug(f"  daily_queue.opened_at: {daily_queue.opened_at}")

            if not daily_queue:
                logger.debug(
                    f"[_check_online_time_restrictions] ❌ DailyQueue НЕ НАЙДЕНА!"
                )
                # Дополнительная диагностика
                all_queues = (
                    self.db.query(DailyQueue)
                    .filter(DailyQueue.specialist_id == qr_token.specialist_id)
                    .all()
                )
                logger.debug(
                    f"[_check_online_time_restrictions] Все очереди для specialist_id={qr_token.specialist_id}:"
                )
                for q in all_queues:
                    logger.debug(f"    - ID={q.id}, day={q.day}, active={q.active}")
                return {"allowed": False, "message": "Очередь не активна"}

            # Проверяем, открыт ли прием
            if daily_queue.opened_at:
                return {
                    "allowed": False,
                    "message": "Запись закрыта - прием уже открыт",
                    "status": "closed_reception_opened",
                }

        # ✅ ИСПРАВЛЕНИЕ: Проверяем время только если это сегодня
        # ⚠️ ВАЖНО: Для общего QR daily_queue может быть None (если очереди еще не созданы)
        # В этом случае мы уже вернули результат выше, так что здесь daily_queue всегда существует
        now = datetime.now()
        today = date.today()

        # Если QR для будущей даты - разрешаем запись
        if target_date > today:
            # ✅ Защита от None для общего QR (хотя мы уже вернули результат выше)
            if daily_queue:
                max_entries = getattr(daily_queue, 'max_online_entries', 15)
                current_entries = (
                    self.db.query(OnlineQueueEntry)
                    .filter(
                        OnlineQueueEntry.queue_id == daily_queue.id,
                        OnlineQueueEntry.source == "online",
                        OnlineQueueEntry.status.in_(["waiting", "called"]),
                    )
                    .count()
                )
            else:
                # Для общего QR без очередей используем значения по умолчанию
                max_entries = 15
                current_entries = 0

            return {
                "allowed": True,
                "message": f"Запись на {target_date.strftime('%d.%m.%Y')} доступна",
                "status": "available",
                "start_time": (
                    getattr(daily_queue, 'online_start_time', '07:00')
                    if daily_queue
                    else '07:00'
                ),
                "end_time": (
                    getattr(daily_queue, 'online_end_time', '09:00')
                    if daily_queue
                    else '09:00'
                ),
                "max_entries": max_entries,
                "current_entries": current_entries,
                "remaining_slots": max_entries - current_entries,
                "target_date": target_date.isoformat(),
            }

        # Если QR для сегодня - проверяем временные ограничения
        # ✅ ИСПРАВЛЕНИЕ: Используем объекты time для сравнения, как в check_queue_time_window
        from app.services.queue_service import QueueBusinessService

        current_time_obj = now.time()
        start_time_obj = QueueBusinessService.ONLINE_QUEUE_START_TIME  # 07:00

        # Проверяем время начала (по умолчанию 07:00)
        if current_time_obj < start_time_obj:
            # Форматируем время для сообщений
            start_time_str = start_time_obj.strftime('%H:%M')
            current_time_str = current_time_obj.strftime('%H:%M')

            # Вычисляем время до открытия
            start_datetime = now.replace(
                hour=start_time_obj.hour,
                minute=start_time_obj.minute,
                second=0,
                microsecond=0,
            )

            # Если время уже прошло сегодня, значит открытие завтра
            if start_datetime <= now:
                start_datetime = start_datetime.replace(day=start_datetime.day + 1)

            time_until_open = start_datetime - now
            minutes_until_open = int(time_until_open.total_seconds() / 60)

            return {
                "allowed": False,
                "message": f"⏰ Онлайн-запись откроется в {start_time_str}. Текущее время: {current_time_str}",
                "status": "before_start_time",
                "start_time": start_time_str,
                "current_time": current_time_str,
                "minutes_until_open": minutes_until_open,
                "opens_at_datetime": start_datetime.isoformat(),
                "countdown_text": f"Откроется через {minutes_until_open} мин",
            }

        # Проверяем время окончания (по умолчанию 09:00)
        # ✅ ИСПРАВЛЕНИЕ: Используем объекты time для сравнения
        # Для времени окончания используем значение из настроек очереди или по умолчанию
        end_time_str = (
            getattr(daily_queue, 'online_end_time', '09:00') if daily_queue else '09:00'
        )
        if end_time_str:
            # Парсим строку времени в объект time
            end_hour, end_minute = map(int, end_time_str.split(':'))
            end_time_obj = (
                datetime.now()
                .replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
                .time()
            )

            if current_time_obj > end_time_obj:
                return {
                    "allowed": False,
                    "message": f"Запись закрыта в {end_time_str}",
                    "status": "after_end_time",
                    "end_time": end_time_str,
                }

        # Проверяем лимит записей
        # ✅ ИСПРАВЛЕНИЕ: Для общего QR не проверяем строгий лимит (будет проверяться при создании записей)
        if qr_token.is_clinic_wide or qr_token.specialist_id is None:
            # Для общего QR используем значения из первой очереди для информации (если есть)
            max_entries = (
                getattr(daily_queue, 'max_online_entries', 15) if daily_queue else 15
            )
            # Подсчитываем общее количество онлайн записей на эту дату
            all_queues_ids = [
                q.id
                for q in self.db.query(DailyQueue)
                .filter(DailyQueue.day == target_date, DailyQueue.active == True)
                .all()
            ]
            current_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id.in_(all_queues_ids),
                    OnlineQueueEntry.source == "online",
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
                if all_queues_ids
                else 0
            )
        else:
            # Для конкретного специалиста проверяем лимит его очереди
            max_entries = getattr(daily_queue, 'max_online_entries', 15)
            current_entries = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == daily_queue.id,
                    OnlineQueueEntry.source == "online",
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
                .count()
            )

            if current_entries >= max_entries:
                return {
                    "allowed": False,
                    "message": f"Достигнут лимит записей ({max_entries})",
                    "status": "limit_reached",
                    "max_entries": max_entries,
                    "current_entries": current_entries,
                }

        # Все проверки пройдены
        # ✅ ИСПРАВЛЕНИЕ: Определяем start_time и end_time для ответа
        start_time_str = (
            getattr(daily_queue, 'online_start_time', '07:00')
            if daily_queue
            else '07:00'
        )
        end_time_str = (
            getattr(daily_queue, 'online_end_time', '09:00') if daily_queue else '09:00'
        )

        return {
            "allowed": True,
            "message": "Запись доступна",
            "status": "available",
            "start_time": start_time_str,
            "end_time": end_time_str,
            "max_entries": max_entries,
            "current_entries": current_entries,
            "remaining_slots": max_entries - current_entries,
        }
