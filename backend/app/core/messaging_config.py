"""
Конфигурация системы сообщений

Содержит правила доступа и настройки для чата между пользователями.
"""


# Правила доступа: кто может писать кому
MESSAGING_PERMISSIONS: dict[str, list[str]] = {
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
    Проверить, может ли отправитель писать получателю (legacy: только по ролям).

    F-002: используйте can_send_message_with_branch() для multi-tenant проверок.
    """
    allowed_recipients = MESSAGING_PERMISSIONS.get(sender_role, [])
    return recipient_role in allowed_recipients


def can_send_message_with_branch(
    sender_role: str,
    recipient_role: str,
    sender_branch_id: int | None = None,
    recipient_branch_id: int | None = None,
) -> bool:
    """
    F-002: tenant-aware проверка прав отправки сообщения.

    Дополнительно к role-based проверке учитывает принадлежность
    отправителя и получателя к одной клинике. Если branch_id не задан
    у одного из пользователей (single-branch / legacy) — проверка
    пропускается (fallback к role-based).
    """
    allowed_recipients = MESSAGING_PERMISSIONS.get(sender_role, [])
    if recipient_role not in allowed_recipients:
        return False

    # Tenant isolation: оба пользователя должны быть в одной клинике
    if sender_branch_id is not None and recipient_branch_id is not None:
        if sender_branch_id != recipient_branch_id:
            return False

    return True

