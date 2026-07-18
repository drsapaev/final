"""Tokens mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


class TokensMixin(QRQueueServiceMixinBase):
    """Tokens methods for QRQueueService."""

    def generate_qr_token(
        self,
        specialist_id: int,
        department: str,
        generated_by_user_id: int,
        expires_hours: int = 24,
        target_date: str | None = None,
        visit_type: str = "paid",
    ) -> dict[str, Any]:
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
            # TEMPORARY: Disable 09:00 check for testing
            if False: # current_time > "09:00":
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


    def get_qr_token_info(self, token: str) -> dict[str, Any] | None:
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
                "[QRQueueService.get_qr_token_info] Запрос информации о токене: token_present=%s, token_length=%d",
                bool(token),
                len(token or ""),
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
                logger.debug("[QRQueueService.get_qr_token_info] Токен найден в БД:")
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
                    "[QRQueueService.get_qr_token_info] Токен вообще не найден в БД!"
                )

            # Используем timezone-aware datetime для сравнения
            qr_token = (
                self.db.query(QueueToken)
                .filter(QueueToken.token == token, QueueToken.active == True)
                .first()
            )

            if not qr_token:
                logger.debug(
                    "[QRQueueService.get_qr_token_info] Токен не найден или неактивен"
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

                # ⭐ ИСПРАВЛЕНО: Считаем длину онлайн-очереди через OnlineQueueEntry
                # Для консистентности с queue_position_notifications.py
                try:
                    # Используем target_date из токена
                    target_date = qr_token.day

                    # Находим DailyQueue для этого специалиста и дня
                    daily_queue = (
                        self.db.query(DailyQueue)
                        .filter(
                            DailyQueue.specialist_id == specialist.id,
                            DailyQueue.day == target_date
                        )
                        .first()
                    )

                    if daily_queue:
                        # Считаем OnlineQueueEntry записи в этой очереди (waiting/called)
                        queue_length = (
                            self.db.query(OnlineQueueEntry)
                            .filter(
                                OnlineQueueEntry.queue_id == daily_queue.id,
                                OnlineQueueEntry.status.in_(["waiting", "called"]),
                            )
                            .count()
                        ) or 0
                    else:
                        queue_length = 0

                    logger.debug(f"[QRQueueService] online_queue_length: {queue_length}")
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
            logger.debug("[QRQueueService.get_qr_token_info] Формируем ответ...")

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

            time_check = self._check_online_time_restrictions(token)
            time_check.setdefault(
                "status",
                "available" if time_check.get("allowed") else "unavailable",
            )
            time_check.setdefault("message", "")

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
                "selectable_specialists": (
                    self._get_clinic_wide_selectable_specialists()
                    if qr_token.is_clinic_wide or qr_token.specialist_id is None
                    else []
                ),
            }
            result.update(time_check)
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


    def get_active_qr_tokens(self, user_id: int) -> list[dict[str, Any]]:
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
                    # QUEUE-AUDIT-28 P0-10: real URL (was clinic.example.com — regression)
                    "qr_url": f"{self._get_frontend_url()}/queue/join/{token.token}",
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


