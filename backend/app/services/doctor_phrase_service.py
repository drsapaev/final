"""
DoctorPhraseService - Сервис извлечения и ранжирования фраз врача

Принцип: это НЕ генерация текста, а поиск и ранжирование 
ранее введённых фраз врача.

Работает как IDE autocomplete, не как ChatGPT.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.doctor_phrase_history import DoctorPhraseHistory


class DoctorPhraseService:
    """
    Сервис для работы с историей фраз врача.
    
    Основные функции:
    1. Извлечение фраз из текста EMR
    2. Индексация фраз в БД
    3. Поиск подсказок по prefix
    4. Ранжирование по частоте и недавности
    """
    
    # Минимальная длина фразы для индексации
    MIN_PHRASE_LENGTH = 10
    
    # Максимальная длина фразы
    MAX_PHRASE_LENGTH = 200
    
    # Разделители фраз
    PHRASE_DELIMITERS = r'[.;!?\n]'
    
    # Поля EMR для индексации
    INDEXABLE_FIELDS = [
        'complaints',
        'anamnesis_morbi', 
        'anamnesis_vitae',
        'examination',
        'diagnosis',
        'treatment',
        'recommendations'
    ]

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # ИЗВЛЕЧЕНИЕ ФРАЗ
    # ============================================
    
    def extract_phrases(self, text: str, field: str) -> List[str]:
        """
        Извлечь фразы из текста.
        
        Разбивает текст на значимые фразы для последующего
        использования в autocomplete.
        
        Args:
            text: Исходный текст
            field: Поле EMR (complaints, diagnosis и т.д.)
            
        Returns:
            Список извлечённых фраз
        """
        if not text or len(text) < self.MIN_PHRASE_LENGTH:
            return []
        
        # Разбиваем на предложения/фразы
        raw_phrases = re.split(self.PHRASE_DELIMITERS, text)
        
        phrases = []
        for phrase in raw_phrases:
            phrase = phrase.strip()
            
            # Фильтруем по длине
            if len(phrase) < self.MIN_PHRASE_LENGTH:
                continue
            if len(phrase) > self.MAX_PHRASE_LENGTH:
                phrase = phrase[:self.MAX_PHRASE_LENGTH]
            
            phrases.append(phrase)
        
        # Также извлекаем подфразы (после запятых) для частых конструкций
        for phrase in phrases.copy():
            subphrases = phrase.split(',')
            for sub in subphrases[1:]:  # Пропускаем первую часть
                sub = sub.strip()
                if len(sub) >= self.MIN_PHRASE_LENGTH:
                    # Добавляем с контекстом (начало = запятая)
                    phrases.append(f", {sub}")
        
        return list(set(phrases))  # Убираем дубликаты

    # ============================================
    # ИНДЕКСАЦИЯ ФРАЗ
    # ============================================
    
    def index_doctor_phrases(
        self, 
        doctor_id: int, 
        emr_data: Dict[str, Any],
        specialty: Optional[str] = None
    ) -> int:
        """
        Проиндексировать фразы врача из EMR записи.
        
        Вызывается после сохранения EMR для обновления
        истории фраз врача.
        
        Args:
            doctor_id: ID врача
            emr_data: Данные EMR (словарь с полями)
            specialty: Специальность врача
            
        Returns:
            Количество добавленных/обновлённых фраз
        """
        indexed_count = 0
        
        for field in self.INDEXABLE_FIELDS:
            text = emr_data.get(field)
            if not text:
                continue
            
            phrases = self.extract_phrases(text, field)
            
            for phrase in phrases:
                self._upsert_phrase(
                    doctor_id=doctor_id,
                    field=field,
                    phrase=phrase,
                    specialty=specialty
                )
                indexed_count += 1
        
        self.db.commit()
        return indexed_count
    
    def _upsert_phrase(
        self,
        doctor_id: int,
        field: str,
        phrase: str,
        specialty: Optional[str] = None
    ) -> DoctorPhraseHistory:
        """Добавить или обновить фразу в истории"""
        
        prefix_index = DoctorPhraseHistory.create_prefix_index(phrase)
        
        # Ищем существующую
        existing = self.db.query(DoctorPhraseHistory).filter(
            DoctorPhraseHistory.doctor_id == doctor_id,
            DoctorPhraseHistory.field == field,
            DoctorPhraseHistory.phrase == phrase
        ).first()
        
        if existing:
            # Увеличиваем счётчик
            existing.usage_count += 1
            existing.last_used = datetime.utcnow()
            return existing
        else:
            # Создаём новую
            new_phrase = DoctorPhraseHistory(
                doctor_id=doctor_id,
                field=field,
                phrase=phrase,
                prefix_index=prefix_index,
                specialty=specialty,
                usage_count=1
            )
            self.db.add(new_phrase)
            return new_phrase

    # ============================================
    # ПОИСК ПОДСКАЗОК
    # ============================================
    
    def suggest_phrases(
        self,
        doctor_id: int,
        field: str,
        current_text: str,
        cursor_position: int,
        specialty: Optional[str] = None,
        max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Найти подсказки для текущего текста.
        
        Это ключевой метод - ищет продолжения фраз
        на основе истории врача.
        
        Args:
            doctor_id: ID врача
            field: Поле EMR
            current_text: Текущий текст в поле
            cursor_position: Позиция курсора
            specialty: Специальность
            max_suggestions: Максимум подсказок
            
        Returns:
            Список подсказок с continuation (хвостом)
        """
        if not current_text or cursor_position == 0:
            return self._get_frequent_phrases(doctor_id, field, specialty, max_suggestions)
        
        # Берём текст до курсора
        text_before_cursor = current_text[:cursor_position]
        
        # Ищем последнюю фразу (после точки, запятой и т.д.)
        last_delimiter = max(
            text_before_cursor.rfind('.'),
            text_before_cursor.rfind(','),
            text_before_cursor.rfind(';'),
            text_before_cursor.rfind('\n')
        )
        
        if last_delimiter >= 0:
            search_text = text_before_cursor[last_delimiter:].strip()
            # Если начинается с запятой, оставляем её
            if text_before_cursor[last_delimiter] == ',':
                search_text = ', ' + search_text.lstrip(', ')
        else:
            search_text = text_before_cursor.strip()
        
        if len(search_text) < 3:
            return self._get_frequent_phrases(doctor_id, field, specialty, max_suggestions)
        
        # Prefix search
        prefix = search_text.lower()[:50]
        
        # Запрос к БД
        query = self.db.query(DoctorPhraseHistory).filter(
            DoctorPhraseHistory.doctor_id == doctor_id,
            DoctorPhraseHistory.field == field,
            DoctorPhraseHistory.prefix_index.like(f"{prefix}%")
        )
        
        if specialty:
            query = query.filter(
                (DoctorPhraseHistory.specialty == specialty) | 
                (DoctorPhraseHistory.specialty.is_(None))
            )
        
        # Ранжирование: частота → недавность
        results = query.order_by(
            desc(DoctorPhraseHistory.usage_count),
            desc(DoctorPhraseHistory.last_used)
        ).limit(max_suggestions * 2).all()
        
        # Формируем ответ с continuation (хвостом)
        suggestions = []
        for phrase_record in results:
            continuation = self._get_continuation(search_text, phrase_record.phrase)
            
            if continuation and len(continuation) > 2:
                suggestions.append({
                    "text": continuation,  # Только хвост!
                    "full_phrase": phrase_record.phrase,
                    "source": "history",
                    "usageCount": phrase_record.usage_count,
                    "lastUsed": phrase_record.last_used.isoformat() if phrase_record.last_used else None
                })
        
        # Убираем дубликаты и ограничиваем
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s["text"] not in seen:
                seen.add(s["text"])
                unique_suggestions.append(s)
                if len(unique_suggestions) >= max_suggestions:
                    break
        
        return unique_suggestions
    
    def _get_continuation(self, prefix: str, full_phrase: str) -> Optional[str]:
        """
        Получить продолжение (хвост) фразы.
        
        Если prefix = "Головная боль"
        И full_phrase = "Головная боль, давящего характера"
        То continuation = ", давящего характера"
        """
        prefix_lower = prefix.lower().strip()
        phrase_lower = full_phrase.lower().strip()
        
        if phrase_lower.startswith(prefix_lower):
            # Возвращаем хвост с оригинальным регистром
            return full_phrase[len(prefix.strip()):]
        
        return None
    
    def _get_frequent_phrases(
        self,
        doctor_id: int,
        field: str,
        specialty: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Получить частые фразы (для пустого поля)"""
        
        query = self.db.query(DoctorPhraseHistory).filter(
            DoctorPhraseHistory.doctor_id == doctor_id,
            DoctorPhraseHistory.field == field
        )
        
        if specialty:
            query = query.filter(
                (DoctorPhraseHistory.specialty == specialty) | 
                (DoctorPhraseHistory.specialty.is_(None))
            )
        
        results = query.order_by(
            desc(DoctorPhraseHistory.usage_count),
            desc(DoctorPhraseHistory.last_used)
        ).limit(limit).all()
        
        return [
            {
                "text": r.phrase,
                "full_phrase": r.phrase,
                "source": "history",
                "usageCount": r.usage_count,
                "lastUsed": r.last_used.isoformat() if r.last_used else None
            }
            for r in results
        ]


# Singleton instance
_service_instance = None

def get_doctor_phrase_service(db: Session) -> DoctorPhraseService:
    """Factory function for DI"""
    return DoctorPhraseService(db)
