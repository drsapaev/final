"""
Общие бизнес-валидаторы для Pydantic schemas

Этот модуль содержит переиспользуемые валидаторы для обеспечения
бизнес-логики на уровне данных.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Any
import re

from pydantic import field_validator


def validate_future_date(v: Optional[date]) -> Optional[date]:
    """
    Проверяет, что дата не в прошлом.
    
    Args:
        v: Дата для проверки
        
    Returns:
        Проверенная дата
        
    Raises:
        ValueError: Если дата в прошлом
    """
    if v is not None and v < date.today():
        raise ValueError("Дата не может быть в прошлом")
    return v


def validate_future_datetime(v: Optional[datetime]) -> Optional[datetime]:
    """
    Проверяет, что дата/время не в прошлом.
    
    Args:
        v: Дата/время для проверки
        
    Returns:
        Проверенная дата/время
        
    Raises:
        ValueError: Если дата/время в прошлом
    """
    if v is not None and v < datetime.now():
        raise ValueError("Дата и время не могут быть в прошлом")
    return v


def validate_date_not_too_far(v: Optional[date], max_days: int = 365) -> Optional[date]:
    """
    Проверяет, что дата не слишком далеко в будущем.
    
    Args:
        v: Дата для проверки
        max_days: Максимальное количество дней в будущем
        
    Returns:
        Проверенная дата
        
    Raises:
        ValueError: Если дата слишком далеко в будущем
    """
    if v is not None:
        max_date = date.today() + timedelta(days=max_days)
        if v > max_date:
            raise ValueError(f"Дата не может быть более чем на {max_days} дней в будущем")
    return v


def validate_phone_format(v: Optional[str]) -> Optional[str]:
    """
    Проверяет и нормализует формат телефона (Узбекистан).
    
    Args:
        v: Номер телефона для проверки
        
    Returns:
        Нормализованный номер телефона
        
    Raises:
        ValueError: Если формат неверный
    """
    if v is not None:
        # Очищаем от лишних символов
        clean = re.sub(r"[^\d+]", "", v)
        
        # Добавляем +998 если начинается с 9
        if clean.startswith("9") and len(clean) == 9:
            clean = "+998" + clean
        
        # Добавляем + если начинается с 998
        if clean.startswith("998") and len(clean) == 12:
            clean = "+" + clean
        
        if not re.match(r"^\+998\d{9}$", clean):
            raise ValueError("Неверный формат телефона. Ожидается: +998XXXXXXXXX")
        return clean
    return v


def validate_email(v: Optional[str]) -> Optional[str]:
    """
    Дополнительная валидация и нормализация email.
    
    Args:
        v: Email для проверки
        
    Returns:
        Нормализованный email (lowercase, stripped)
        
    Raises:
        ValueError: Если формат неверный
    """
    if v is not None:
        v = v.lower().strip()
        if not re.match(r"^[\w\.\-\+]+@[\w\.\-]+\.\w{2,}$", v):
            raise ValueError("Неверный формат email")
    return v


def validate_positive_number(v: Optional[float], field_name: str = "Значение") -> Optional[float]:
    """
    Проверяет, что число положительное.
    
    Args:
        v: Число для проверки
        field_name: Название поля для сообщения об ошибке
        
    Returns:
        Проверенное число
        
    Raises:
        ValueError: Если число не положительное
    """
    if v is not None and v <= 0:
        raise ValueError(f"{field_name} должно быть положительным числом")
    return v


def validate_non_negative_number(v: Optional[float], field_name: str = "Значение") -> Optional[float]:
    """
    Проверяет, что число неотрицательное.
    
    Args:
        v: Число для проверки
        field_name: Название поля для сообщения об ошибке
        
    Returns:
        Проверенное число
        
    Raises:
        ValueError: Если число отрицательное
    """
    if v is not None and v < 0:
        raise ValueError(f"{field_name} не может быть отрицательным")
    return v


def validate_string_length(
    v: Optional[str], 
    min_length: int = 0, 
    max_length: int = 1000,
    field_name: str = "Текст"
) -> Optional[str]:
    """
    Проверяет длину строки.
    
    Args:
        v: Строка для проверки
        min_length: Минимальная длина
        max_length: Максимальная длина
        field_name: Название поля для сообщения об ошибке
        
    Returns:
        Проверенная строка (stripped)
        
    Raises:
        ValueError: Если длина не соответствует ограничениям
    """
    if v is not None:
        v = v.strip()
        if len(v) < min_length:
            raise ValueError(f"{field_name} должен содержать минимум {min_length} символов")
        if len(v) > max_length:
            raise ValueError(f"{field_name} не должен превышать {max_length} символов")
    return v


def validate_inn(v: Optional[str]) -> Optional[str]:
    """
    Проверяет формат ИНН (Узбекистан - 9 цифр).
    
    Args:
        v: ИНН для проверки
        
    Returns:
        Проверенный ИНН
        
    Raises:
        ValueError: Если формат неверный
    """
    if v is not None:
        clean = re.sub(r"\D", "", v)
        if len(clean) != 9:
            raise ValueError("ИНН должен содержать 9 цифр")
        return clean
    return v


def sanitize_html(v: Optional[str]) -> Optional[str]:
    """
    Удаляет потенциально опасные HTML теги из строки.
    
    Args:
        v: Строка для очистки
        
    Returns:
        Очищенная строка
    """
    if v is not None:
        # Удаляем script и style теги с их содержимым
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'<style[^>]*>.*?</style>', '', v, flags=re.IGNORECASE | re.DOTALL)
        # Удаляем on* атрибуты (onclick, onload, etc.)
        v = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', v, flags=re.IGNORECASE)
        # Удаляем javascript: URLs
        v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
    return v
