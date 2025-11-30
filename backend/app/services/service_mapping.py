"""
Service code normalization utilities
"""
from typing import Dict, Any


def normalize_service_code(code: str) -> str:
    """
    Нормализует код услуги к единому формату

    Args:
        code: Код услуги (например, "LAB-001", "lab_001", "LAB 001")

    Returns:
        Нормализованный код (нижний регистр, замена пробелов и тире на подчеркивания)

    Examples:
        >>> normalize_service_code("LAB-001")
        'lab_001'
        >>> normalize_service_code("LAB 001")
        'lab_001'
        >>> normalize_service_code("CONS_CARDIO")
        'cons_cardio'
    """
    if not code:
        return ""

    # Приводим к нижнему регистру
    normalized = code.lower()

    # Заменяем пробелы и тире на подчеркивания
    normalized = normalized.replace(" ", "_").replace("-", "_")

    # Убираем множественные подчеркивания
    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    # Убираем подчеркивания в начале и конце
    normalized = normalized.strip("_")

    return normalized


def get_service_code(service_data: Dict[str, Any]) -> str:
    """
    Извлекает код услуги из различных полей
    
    ВАЖНО: Для формата 'K01', 'D01', 'L01' (SSOT формат из БД) сохраняет регистр.
    Для других форматов нормализует к нижнему регистру.

    Args:
        service_data: Словарь с данными услуги (может содержать 'code', 'service_code', 'category_code')

    Returns:
        Код услуги в правильном формате или пустую строку

    Examples:
        >>> get_service_code({"service_code": "K01"})
        'K01'  # SSOT формат - регистр сохранен
        >>> get_service_code({"code": "LAB-001"})
        'lab_001'  # Старый формат - нормализован
        >>> get_service_code({"service_code": "CONS_CARDIO"})
        'cons_cardio'  # Старый формат - нормализован
    """
    if not service_data:
        return ""

    # Пробуем извлечь код из разных полей (в порядке приоритета)
    # Приоритет: service_code (SSOT) > code > category_code
    service_code = service_data.get("service_code")
    code = service_data.get("code")
    category_code = service_data.get("category_code")
    
    # Если есть service_code в формате SSOT (K01, D01, L01 и т.д.), возвращаем как есть
    if service_code:
        # ✅ ИСПРАВЛЕНО Bug 2: Проверяем формат SSOT независимо от регистра (K01, k01, D01, d01 и т.д.)
        # Формат SSOT: одна буква (любой регистр) + одна или две цифры
        import re
        # Нормализуем к верхнему регистру для проверки, но сохраняем оригинальный регистр
        if re.match(r'^[A-Za-z]\d{1,2}$', service_code):
            # Это SSOT формат - нормализуем к верхнему регистру для консистентности
            # (K01, k01 -> K01; D01, d01 -> D01)
            return service_code.upper()
    
    # Для остальных случаев используем нормализацию
    code_to_normalize = service_code or code or category_code or ""
    
    if code_to_normalize:
        return normalize_service_code(code_to_normalize)
    
    return ""