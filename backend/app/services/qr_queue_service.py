"""
Сервис для управления QR очередями
"""
import secrets
import qrcode
import io
import base64
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.online_queue import (
    DailyQueue, OnlineQueueEntry, QueueToken, 
    QueueJoinSession, QueueStatistics
)
from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.user import User
from app.services.feature_flags import is_feature_enabled


class QRQueueService:
    """Сервис для управления QR очередями"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_qr_token(
        self,
        specialist_id: int,
        department: str,
        generated_by_user_id: int,
        expires_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Генерирует QR токен для присоединения к очереди
        
        Args:
            specialist_id: ID специалиста
            department: Отделение
            generated_by_user_id: ID пользователя, создавшего токен
            expires_hours: Время жизни токена в часах
            
        Returns:
            Словарь с данными токена и QR кодом
        """
        # Генерируем уникальный токен
        token = secrets.token_urlsafe(32)
        
        # Создаем запись токена
        qr_token = QueueToken(
            token=token,
            day=date.today(),
            specialist_id=specialist_id,
            department=department,
            generated_by_user_id=generated_by_user_id,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )
        
        self.db.add(qr_token)
        self.db.commit()
        
        # Генерируем QR код
        qr_url = f"https://clinic.example.com/queue/join/{token}"
        qr_code_data = self._generate_qr_code(qr_url)
        
        return {
            "token": token,
            "qr_url": qr_url,
            "qr_code_base64": qr_code_data,
            "specialist_id": specialist_id,
            "department": department,
            "expires_at": qr_token.expires_at.isoformat(),
            "active": qr_token.active
        }
    
    def get_qr_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о QR токене
        
        Args:
            token: QR токен
            
        Returns:
            Информация о токене или None если не найден
        """
        qr_token = self.db.query(QueueToken).filter(
            QueueToken.token == token,
            QueueToken.active == True,
            QueueToken.expires_at > datetime.utcnow()
        ).first()
        
        if not qr_token:
            return None
        
        # Получаем информацию о специалисте
        specialist = self.db.query(Doctor).filter(Doctor.id == qr_token.specialist_id).first()
        
        # Получаем текущую очередь
        today = date.today()
        daily_queue = self.db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == qr_token.specialist_id,
            DailyQueue.active == True
        ).first()
        
        # Подсчитываем текущую длину очереди
        queue_length = 0
        if daily_queue:
            queue_length = self.db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.status.in_(["waiting", "called"])
            ).count()
        
        return {
            "token": token,
            "specialist_id": qr_token.specialist_id,
            "specialist_name": getattr(specialist, 'name', getattr(specialist, 'full_name', f"Врач ID {qr_token.specialist_id}")) if specialist else "Неизвестный специалист",
            "department": qr_token.department,
            "department_name": self._get_department_name(qr_token.department),
            "queue_length": queue_length,
            "queue_active": daily_queue is not None and daily_queue.active,
            "expires_at": qr_token.expires_at.isoformat()
        }
    
    def start_join_session(
        self,
        token: str,
        ip_address: str = None,
        user_agent: str = None
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
        # Проверяем токен
        token_info = self.get_qr_token_info(token)
        if not token_info:
            raise ValueError("Недействительный или истекший QR токен")
        
        if not token_info["queue_active"]:
            raise ValueError("Очередь в данный момент не активна")
        
        # Проверяем временные ограничения
        time_check = self._check_online_time_restrictions(token)
        if not time_check["allowed"]:
            raise ValueError(time_check["message"])
        
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
            expires_at=datetime.utcnow() + timedelta(minutes=15)  # 15 минут на заполнение
        )
        
        self.db.add(session)
        self.db.commit()
        
        # Добавляем информацию о времени в ответ
        token_info.update(time_check)
        
        return {
            "session_token": session_token,
            "expires_at": session.expires_at.isoformat(),
            "queue_info": token_info
        }
    
    def complete_join_session(
        self,
        session_token: str,
        patient_name: str,
        phone: str,
        telegram_id: Optional[int] = None
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
        session = self.db.query(QueueJoinSession).filter(
            QueueJoinSession.session_token == session_token,
            QueueJoinSession.status == "pending",
            QueueJoinSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            raise ValueError("Сессия не найдена или истекла")
        
        # Получаем информацию о токене
        qr_token = self.db.query(QueueToken).filter(
            QueueToken.token == session.qr_token
        ).first()
        
        if not qr_token:
            raise ValueError("QR токен не найден")
        
        # Проверяем дубликаты по телефону в сегодняшней очереди
        today = date.today()
        daily_queue = self.db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == qr_token.specialist_id,
            DailyQueue.active == True
        ).first()
        
        if not daily_queue:
            raise ValueError("Очередь не активна")
        
        # Проверяем дубликат
        existing_entry = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.phone == phone,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).first()
        
        if existing_entry:
            raise ValueError(f"Пациент с телефоном {phone} уже в очереди под номером {existing_entry.number}")
        
        # Получаем следующий номер в очереди
        next_number = self._get_next_queue_number(daily_queue.id)
        
        # Пытаемся найти существующего пациента
        patient = self.db.query(Patient).filter(Patient.phone == phone).first()
        
        # Создаем запись в очереди
        queue_entry = OnlineQueueEntry(
            queue_id=daily_queue.id,
            number=next_number,
            patient_id=patient.id if patient else None,
            patient_name=patient_name,
            phone=phone,
            telegram_id=telegram_id,
            source="online"
        )
        
        self.db.add(queue_entry)
        
        # Обновляем сессию
        session.status = "joined"
        session.patient_name = patient_name
        session.phone = phone
        session.telegram_id = telegram_id
        session.queue_entry_id = queue_entry.id
        session.queue_number = next_number
        session.joined_at = datetime.utcnow()
        
        self.db.commit()
        
        # Обновляем статистику
        self._update_queue_statistics(daily_queue.id, "online_joins")
        
        return {
            "success": True,
            "queue_number": next_number,
            "queue_length": self._get_queue_length(daily_queue.id),
            "estimated_wait_time": self._estimate_wait_time(daily_queue.id, next_number),
            "specialist_name": getattr(qr_token.specialist, 'name', getattr(qr_token.specialist, 'full_name', f"Врач ID {qr_token.specialist_id}")) if qr_token.specialist else "Неизвестный специалист",
            "department": qr_token.department
        }
    
    def get_queue_status(self, specialist_id: int, target_date: date = None) -> Dict[str, Any]:
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
        
        daily_queue = self.db.query(DailyQueue).filter(
            DailyQueue.day == target_date,
            DailyQueue.specialist_id == specialist_id
        ).first()
        
        if not daily_queue:
            return {
                "active": False,
                "queue_length": 0,
                "current_number": None,
                "entries": []
            }
        
        # Получаем записи в очереди
        entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id
        ).order_by(OnlineQueueEntry.number).all()
        
        # Находим текущий номер (последний вызванный или обслуженный)
        current_number = None
        last_served = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.status.in_(["called", "served"])
        ).order_by(OnlineQueueEntry.number.desc()).first()
        
        if last_served:
            current_number = last_served.number
        
        return {
            "active": daily_queue.active,
            "queue_length": len([e for e in entries if e.status in ["waiting", "called"]]),
            "current_number": current_number,
            "entries": [
                {
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None
                }
                for entry in entries
            ]
        }
    
    def call_next_patient(self, specialist_id: int, called_by_user_id: int) -> Dict[str, Any]:
        """
        Вызывает следующего пациента в очереди
        
        Args:
            specialist_id: ID специалиста
            called_by_user_id: ID пользователя, вызвавшего пациента
            
        Returns:
            Информация о вызванном пациенте
        """
        today = date.today()
        daily_queue = self.db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == specialist_id,
            DailyQueue.active == True
        ).first()
        
        if not daily_queue:
            raise ValueError("Очередь не активна")
        
        # Находим следующего пациента в статусе "waiting"
        next_patient = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.status == "waiting"
        ).order_by(OnlineQueueEntry.number).first()
        
        if not next_patient:
            return {
                "success": False,
                "message": "Нет пациентов в очереди"
            }
        
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
                "source": next_patient.source
            },
            "queue_length": self._get_queue_length(daily_queue.id)
        }
    
    def get_active_qr_tokens(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает активные QR токены пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список активных токенов
        """
        tokens = self.db.query(QueueToken).filter(
            QueueToken.generated_by_user_id == user_id,
            QueueToken.active == True,
            QueueToken.expires_at > datetime.utcnow()
        ).order_by(QueueToken.created_at.desc()).all()
        
        result = []
        for token in tokens:
            # Получаем статистику использования
            sessions_count = self.db.query(QueueJoinSession).filter(
                QueueJoinSession.qr_token == token.token
            ).count()
            
            successful_joins = self.db.query(QueueJoinSession).filter(
                QueueJoinSession.qr_token == token.token,
                QueueJoinSession.status == "joined"
            ).count()
            
            result.append({
                "token": token.token,
                "specialist_id": token.specialist_id,
                "department": token.department,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat(),
                "sessions_count": sessions_count,
                "successful_joins": successful_joins,
                "qr_url": f"https://clinic.example.com/queue/join/{token.token}"
            })
        
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
        qr_token = self.db.query(QueueToken).filter(
            QueueToken.token == token,
            QueueToken.generated_by_user_id == user_id,
            QueueToken.active == True
        ).first()
        
        if not qr_token:
            return False
        
        qr_token.active = False
        self.db.commit()
        
        return True
    
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
    
    def _get_next_queue_number(self, queue_id: int) -> int:
        """Получает следующий номер в очереди"""
        last_entry = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue_id
        ).order_by(OnlineQueueEntry.number.desc()).first()
        
        return (last_entry.number + 1) if last_entry else 1
    
    def _get_queue_length(self, queue_id: int) -> int:
        """Получает текущую длину очереди"""
        return self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
    
    def _estimate_wait_time(self, queue_id: int, queue_number: int) -> int:
        """Оценивает время ожидания в минутах"""
        # Простая оценка: 15 минут на пациента
        waiting_before = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.number < queue_number,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
        
        return waiting_before * 15
    
    def _get_department_name(self, department: str) -> str:
        """Получает человекочитаемое название отделения"""
        department_names = {
            "cardiology": "Кардиология",
            "dermatology": "Дерматология", 
            "dentistry": "Стоматология",
            "laboratory": "Лаборатория",
            "ecg": "ЭКГ",
            "general": "Общая практика"
        }
        return department_names.get(department, department.title())
    
    def _update_queue_statistics(self, queue_id: int, stat_field: str):
        """Обновляет статистику очереди"""
        today = date.today()
        
        stats = self.db.query(QueueStatistics).filter(
            QueueStatistics.queue_id == queue_id,
            QueueStatistics.date == today
        ).first()
        
        if not stats:
            stats = QueueStatistics(
                queue_id=queue_id,
                date=today
            )
            self.db.add(stats)
        
        # Увеличиваем счетчик
        current_value = getattr(stats, stat_field, 0)
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
        
        # Получаем очередь
        today = date.today()
        daily_queue = self.db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == qr_token.specialist_id,
            DailyQueue.active == True
        ).first()
        
        if not daily_queue:
            return {"allowed": False, "message": "Очередь не активна"}
        
        # Проверяем, открыт ли прием
        if daily_queue.opened_at:
            return {
                "allowed": False, 
                "message": "Запись закрыта - прием уже открыт",
                "status": "closed_reception_opened"
            }
        
        # Получаем текущее время
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Проверяем время начала (по умолчанию 07:00)
        start_time = getattr(daily_queue, 'online_start_time', '07:00')
        if current_time < start_time:
            return {
                "allowed": False,
                "message": f"Запись откроется в {start_time}",
                "status": "before_start_time",
                "start_time": start_time
            }
        
        # Проверяем время окончания (по умолчанию 09:00)
        end_time = getattr(daily_queue, 'online_end_time', '09:00')
        if end_time and current_time > end_time:
            return {
                "allowed": False,
                "message": f"Запись закрыта в {end_time}",
                "status": "after_end_time",
                "end_time": end_time
            }
        
        # Проверяем лимит записей
        max_entries = getattr(daily_queue, 'max_online_entries', 15)
        current_entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.source == "online",
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
        
        if current_entries >= max_entries:
            return {
                "allowed": False,
                "message": f"Достигнут лимит записей ({max_entries})",
                "status": "limit_reached",
                "max_entries": max_entries,
                "current_entries": current_entries
            }
        
        # Все проверки пройдены
        return {
            "allowed": True,
            "message": "Запись доступна",
            "status": "available",
            "start_time": start_time,
            "end_time": end_time,
            "max_entries": max_entries,
            "current_entries": current_entries,
            "remaining_slots": max_entries - current_entries
        }
