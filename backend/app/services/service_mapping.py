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
    Извлекает и нормализует код услуги из различных полей

    Args:
        service_data: Словарь с данными услуги (может содержать 'code', 'service_code', 'category_code')

    Returns:
        Нормализованный код услуги или пустую строку

    Examples:
        >>> get_service_code({"code": "LAB-001"})
        'lab_001'
        >>> get_service_code({"service_code": "CONS_CARDIO"})
        'cons_cardio'
        >>> get_service_code({"category_code": "PROCEDURES"})
        'procedures'
    """
    if not service_data:
        return ""

    # Пробуем извлечь код из разных полей (в порядке приоритета)
    code = (
        service_data.get("code") or
        service_data.get("service_code") or
        service_data.get("category_code") or
        ""
    )

    return normalize_service_code(code) if code else ""