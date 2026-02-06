"""
Конфигурация системы сообщений

Содержит правила доступа и настройки для чата между пользователями.
"""

from typing import Dict, List


# Правила доступа: кто может писать кому
MESSAGING_PERMISSIONS: Dict[str, List[str]] = {
    # Админы могут писать всем
    "Admin": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient", 
              "cardio", "derma", "dentist"],
    
    # Врачи могут писать пациентам и персоналу
    "Doctor": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
               "cardio", "derma", "dentist"],
    "cardio": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
               "cardio", "derma", "dentist"],
    "derma": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
              "cardio", "derma", "dentist"],
    "dentist": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
                "cardio", "derma", "dentist"],
    
    # Регистраторы могут писать персоналу и пациентам
    "Registrar": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
                  "cardio", "derma", "dentist"],
    
    # Кассиры и лаборанты - персоналу
    "Cashier": ["Admin", "Doctor", "Registrar", "Cashier", "Lab",
                "cardio", "derma", "dentist"],
    "Lab": ["Admin", "Doctor", "Registrar", "Cashier", "Lab",
            "cardio", "derma", "dentist"],
    
    # Пациенты могут писать врачам, админам и регистраторам
    "Patient": ["Admin", "Doctor", "Registrar", "cardio", "derma", "dentist"],
}


# Настройки WebSocket
WEBSOCKET_HEARTBEAT_INTERVAL = 30  # секунд
WEBSOCKET_PING_TIMEOUT = 10  # секунд


def can_send_message(sender_role: str, recipient_role: str) -> bool:
    """
    Проверить, может ли отправитель писать получателю.
    
    Args:
        sender_role: Роль отправителя
        recipient_role: Роль получателя
        
    Returns:
        True если отправка разрешена
    """
    allowed_recipients = MESSAGING_PERMISSIONS.get(sender_role, [])
    return recipient_role in allowed_recipients
