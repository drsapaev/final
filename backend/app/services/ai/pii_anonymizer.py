"""
PII Anonymizer - Удаление персональных данных перед отправкой в AI API.

HIPAA/GDPR compliance: не отправляем имена, ID, телефоны, адреса во внешние AI.
"""

import logging
import re
from typing import Any, Dict, List, Set

from .ai_interfaces import IAnonymizer

logger = logging.getLogger(__name__)


# Поля, которые нужно полностью удалить
PII_FIELDS_TO_REMOVE: Set[str] = {
    # Идентификаторы
    "patient_id",
    "patient_name",
    "user_id",
    "doctor_id",
    "visit_id",
    "emr_id",
    
    # Контакты
    "phone",
    "phone_number",
    "mobile",
    "email",
    "email_address",
    
    # Адреса
    "address",
    "home_address",
    "work_address",
    "city",
    "street",
    
    # Документы
    "passport",
    "passport_number",
    "inn",
    "snils",
    "insurance_number",
    "insurance_policy",
    
    # Имена
    "name",
    "full_name",
    "first_name",
    "last_name",
    "middle_name",
    "father_name",
    
    # Другие
    "iin",  # ИИН
    "birth_date",  # Точная дата рождения
    "date_of_birth",
}

# Поля для маскировки (преобразуем, но не удаляем)
PII_FIELDS_TO_MASK: Dict[str, str] = {
    "patient_age": "patient_age_group",  # 35 -> "30-39"
    "age": "age_group",
}


class PIIAnonymizer(IAnonymizer):
    """
    Анонимизация персональных данных для AI запросов.
    
    Стратегии:
    1. Удаление: имена, ID, контакты
    2. Маскировка: возраст -> возрастная группа
    3. Замена: конкретные даты -> относительные ("вчера", "2 недели назад")
    """
    
    def __init__(self):
        self._anonymized_fields: List[str] = []
        self._removed_fields: List[str] = []
    
    def anonymize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Удаляет/маскирует PII из данных.
        
        Args:
            data: Исходные данные с потенциальным PII
            
        Returns:
            Очищенные данные, безопасные для отправки в AI API
        """
        self._anonymized_fields = []
        self._removed_fields = []
        
        if not data:
            return {}
        
        result = self._process_dict(data)
        
        if self._removed_fields:
            logger.info(
                f"PII Anonymizer: removed {len(self._removed_fields)} fields: "
                f"{', '.join(self._removed_fields[:5])}{'...' if len(self._removed_fields) > 5 else ''}"
            )
        
        return result
    
    def _process_dict(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Рекурсивная обработка словаря"""
        result = {}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            # Проверяем на удаление
            if self._should_remove(key):
                self._removed_fields.append(full_key)
                continue
            
            # Проверяем на маскировку
            if key in PII_FIELDS_TO_MASK:
                new_key = PII_FIELDS_TO_MASK[key]
                result[new_key] = self._mask_value(key, value)
                self._anonymized_fields.append(f"{full_key} -> {new_key}")
                continue
            
            # Рекурсивная обработка вложенных структур
            if isinstance(value, dict):
                result[key] = self._process_dict(value, full_key)
            elif isinstance(value, list):
                result[key] = self._process_list(value, full_key)
            elif isinstance(value, str):
                # Проверяем текст на случайный PII
                result[key] = self._sanitize_text(value)
            else:
                result[key] = value
        
        return result
    
    def _process_list(self, items: List[Any], prefix: str) -> List[Any]:
        """Обработка списка"""
        result = []
        for i, item in enumerate(items):
            if isinstance(item, dict):
                result.append(self._process_dict(item, f"{prefix}[{i}]"))
            elif isinstance(item, str):
                result.append(self._sanitize_text(item))
            else:
                result.append(item)
        return result
    
    def _should_remove(self, key: str) -> bool:
        """Проверка, нужно ли удалить поле"""
        key_lower = key.lower()
        return key_lower in PII_FIELDS_TO_REMOVE or any(
            pii in key_lower for pii in ["patient_name", "phone", "email", "passport", "address"]
        )
    
    def _mask_value(self, field: str, value: Any) -> Any:
        """Маскировка значения"""
        if field in ("patient_age", "age"):
            return self._mask_age(value)
        return value
    
    def _mask_age(self, age: Any) -> str:
        """Преобразование возраста в возрастную группу"""
        try:
            age_int = int(age)
            decade = (age_int // 10) * 10
            return f"{decade}-{decade + 9}"
        except (ValueError, TypeError):
            return "unknown"
    
    def _sanitize_text(self, text: str) -> str:
        """
        Очистка текста от случайного PII.
        
        Паттерны:
        - Телефоны: +998 XX XXX XX XX
        - Email: user@domain.com
        - ИИН: 12 цифр
        """
        if not text:
            return text
        
        # Телефоны (международный формат)
        text = re.sub(
            r'\+?[0-9]{1,3}[-.\s]?[0-9]{2,3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{2}[-.\s]?[0-9]{2}',
            '[PHONE]',
            text
        )
        
        # Email
        text = re.sub(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            '[EMAIL]',
            text
        )
        
        # ИИН (12 цифр)
        text = re.sub(
            r'\b[0-9]{12}\b',
            '[IIN]',
            text
        )
        
        return text
    
    def get_anonymized_fields(self) -> List[str]:
        """Возвращает список полей, которые были анонимизированы"""
        return self._anonymized_fields
    
    def get_removed_fields(self) -> List[str]:
        """Возвращает список удаленных полей"""
        return self._removed_fields


# Singleton instance
_anonymizer: PIIAnonymizer = None


def get_anonymizer() -> PIIAnonymizer:
    """Get singleton PII anonymizer instance"""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = PIIAnonymizer()
    return _anonymizer
