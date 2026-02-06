"""
Service code normalization utilities (SSOT - Single Source of Truth)

Этот модуль является ЕДИНСТВЕННЫМ источником истины для:
1. Нормализации кодов услуг
2. Маппинга specialty (queue_tag) -> service_id
3. Получения дефолтной услуги для QR-записей
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ============================================================================
# SSOT: Маппинг specialty -> service lookup parameters
# Используется когда нужно найти услугу по специальности (для QR-записей)
# ============================================================================
SPECIALTY_ALIASES = {
    # Кардиология
    "cardio": "cardiology",
    "heart": "cardiology",
    # Дерматология
    "derma": "dermatology",
    "skin": "dermatology",
    # Стоматология
    "dentist": "stomatology",
    "dental": "stomatology",
    "teeth": "stomatology",
    # Лаборатория
    "lab": "laboratory",
    "labs": "laboratory",
    # Процедуры
    "proc": "procedures",
    "physio": "procedures",
}

# ============================================================================
# SSOT: Группировка услуг по очередям (Shared Queues)
# Определяет какие услуги относятся к какому отделению/вкладке регистратуры
# ============================================================================
QUEUE_GROUPS = {
    "cardiology": {
        "display_name": "Кардиология",
        "display_name_uz": "Kardiologiya",
        "service_codes": ["K01", "K11"],  # Консультация + ЭхоКГ
        "service_prefixes": ["K"],  # Все K-коды кроме K10
        "exclude_codes": ["K10"],  # K10 = ЭКГ - отдельная вкладка
        "queue_tag": "cardiology",
        "tab_key": "cardio",
    },
    "ecg": {
        "display_name": "ЭКГ",
        "display_name_uz": "EKG",
        "service_codes": ["K10"],  # K10 is the standard code for ЭКГ
        "service_prefixes": [],
        "exclude_codes": [],
        "queue_tag": "echokg",
        "tab_key": "echokg",
    },
    "dermatology": {
        "display_name": "Дерматология",
        "display_name_uz": "Dermatologiya",
        "service_codes": ["D01"],  # Только консультация
        "service_prefixes": ["D"],
        "exclude_codes": ["D_PROC"],  # D_PROC = процедуры
        "queue_tag": "dermatology",
        "tab_key": "derma",
    },
    "dental": {
        "display_name": "Стоматология",
        "display_name_uz": "Stomatologiya",
        "service_codes": ["S01", "S10"],  # Консультация + рентген зубов
        "service_prefixes": ["S"],
        "exclude_codes": [],
        "queue_tag": "stomatology",
        "tab_key": "dental",
    },
    "laboratory": {
        "display_name": "Лаборатория",
        "display_name_uz": "Laboratoriya",
        "service_codes": ["L00", "L01", "L02", "L11", "L20", "L23", "L65"],
        "service_prefixes": ["L"],
        "exclude_codes": [],
        "queue_tag": "laboratory",
        "tab_key": "lab",
    },
    "procedures": {
        "display_name": "Процедуры",
        "display_name_uz": "Protseduralar",
        "service_codes": ["P01", "P02", "P05", "C01", "C03", "C05", "C12", "D_PROC01", "D_PROC02"],
        "service_prefixes": ["P", "C", "D_PROC"],
        "exclude_codes": [],
        "queue_tag": "procedures",
        "tab_key": "procedures",
    },
}


def get_queue_group_for_service(code: str) -> Optional[str]:
    """
    SSOT: Определяет к какой группе очереди относится услуга.
    
    Args:
        code: Код услуги (K01, D01, L02, D_PROC02 и т.д.)
        
    Returns:
        Ключ группы очереди (cardiology, dermatology, laboratory и т.д.) или None
        
    Examples:
        >>> get_queue_group_for_service("K01")
        'cardiology'
        >>> get_queue_group_for_service("K10")
        'ecg'
        >>> get_queue_group_for_service("D_PROC02")
        'procedures'
    """
    if not code:
        return None
    
    code_upper = code.upper()
    
    for group_key, group_data in QUEUE_GROUPS.items():
        # Проверяем точное совпадение с service_codes
        if code_upper in [c.upper() for c in group_data.get("service_codes", [])]:
            return group_key
        
        # Проверяем по префиксам (но исключаем exclude_codes)
        exclude_codes = [c.upper() for c in group_data.get("exclude_codes", [])]
        if code_upper in exclude_codes:
            continue
            
        for prefix in group_data.get("service_prefixes", []):
            if code_upper.startswith(prefix.upper()):
                # Проверяем что код не в списке исключений
                is_excluded = any(code_upper.startswith(exc.upper()) for exc in exclude_codes)
                if not is_excluded:
                    return group_key
    
    return None


def get_services_for_department(department_key: str) -> Dict[str, Any]:
    """
    SSOT: Получает информацию о группе услуг для отделения.
    
    Args:
        department_key: Ключ отделения (cardio, derma, lab, dental, echokg, procedures)
        
    Returns:
        Словарь с информацией о группе или пустой словарь
        
    Examples:
        >>> get_services_for_department("cardio")
        {'display_name': 'Кардиология', 'service_codes': ['K01', 'K11'], ...}
    """
    # Маппинг tab_key -> group_key
    tab_to_group = {group["tab_key"]: key for key, group in QUEUE_GROUPS.items()}
    
    group_key = tab_to_group.get(department_key, department_key)
    return QUEUE_GROUPS.get(group_key, {})

def normalize_specialty(specialty: str) -> str:
    """
    Нормализует specialty к каноническому виду.
    
    Args:
        specialty: Входная специальность (может быть алиасом)
        
    Returns:
        Каноническое название specialty
        
    Examples:
        >>> normalize_specialty("derma")
        'dermatology'
        >>> normalize_specialty("cardiology")
        'cardiology'
    """
    if not specialty:
        return ""
    normalized = specialty.lower().strip()
    return SPECIALTY_ALIASES.get(normalized, normalized)


def get_default_service_by_specialty(db: "Session", specialty: str) -> Optional[Dict[str, Any]]:
    """
    SSOT: Получает дефолтную консультационную услугу по specialty.
    
    Это ЕДИНСТВЕННЫЙ правильный способ найти услугу для QR-записи.
    Ищет по queue_tag с приоритетом is_consultation=True.
    
    Args:
        db: Сессия БД
        specialty: Specialty (queue_tag) из QR-записи (например "dermatology", "cardiology")
        
    Returns:
        Dict с данными услуги или None:
        {
            "id": int,
            "name": str,
            "service_code": str,
            "price": Decimal,
            "category_code": str,
            "queue_tag": str
        }
        
    Examples:
        >>> service = get_default_service_by_specialty(db, "dermatology")
        >>> service["id"]
        1
        >>> service["name"]
        'Консультация дерматолога'
    """
    from app.models.service import Service
    
    # Нормализуем specialty
    normalized = normalize_specialty(specialty)
    if not normalized:
        logger.warning("get_default_service_by_specialty: пустой specialty")
        return None
    
    # Ищем консультацию по queue_tag
    service = (
        db.query(Service)
        .filter(
            Service.queue_tag == normalized,
            Service.is_consultation == True,
            Service.active == True
        )
        .first()
    )
    
    # Fallback: ищем любую активную услугу с этим queue_tag
    if not service:
        service = (
            db.query(Service)
            .filter(
                Service.queue_tag == normalized,
                Service.active == True
            )
            .first()
        )
    
    # Fallback 2: ищем по category_code (K, D, L, S, C)
    if not service:
        category_mapping = {
            "cardiology": "K",
            "dermatology": "D",
            "laboratory": "L",
            "stomatology": "S",
            "cosmetology": "C",
            "procedures": "P",
        }
        category_code = category_mapping.get(normalized)
        if category_code:
            service = (
                db.query(Service)
                .filter(
                    Service.category_code == category_code,
                    Service.is_consultation == True,
                    Service.active == True
                )
                .first()
            )
            if not service:
                service = (
                    db.query(Service)
                    .filter(
                        Service.category_code == category_code,
                        Service.active == True
                    )
                    .first()
                )
    
    if not service:
        logger.warning(f"get_default_service_by_specialty: услуга не найдена для specialty={specialty}")
        return None
    
    return {
        "id": service.id,
        "name": service.name,
        "service_code": service.service_code,
        "price": service.price,
        "category_code": service.category_code,
        "queue_tag": service.queue_tag,
    }


def normalize_service_code(code: str) -> str:
    """
    Нормализует код услуги к единому формату

    Args:
        code: Код услуги (например, "K11", "LAB-001", "lab_001", "LAB 001")

    Returns:
        Нормализованный код:
        - Для SSOT формата (K01, D02) - UPPERCASE (K11)
        - Для других форматов - lowercase с подчеркиваниями (lab_001)

    Examples:
        >>> normalize_service_code("K11")
        'K11'
        >>> normalize_service_code("k11")
        'K11'
        >>> normalize_service_code("LAB-001")
        'lab_001'
        >>> normalize_service_code("CONS_CARDIO")
        'cons_cardio'
    """
    if not code:
        return ""

    code_stripped = code.strip()
    
    # ⭐ SSOT формат: одна буква + 1-2 цифры (K01, D02, L14, etc.)
    # Эти коды должны быть в UPPERCASE
    import re
    if re.match(r'^[A-Za-z]\d{1,2}$', code_stripped):
        return code_stripped.upper()  # K11, k11 -> K11

    # Для остальных форматов - нормализация к lowercase
    normalized = code_stripped.lower()

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
