"""Validate the authenticated Telegram sender of a patient message."""

from typing import Any


def is_private_patient_message(message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    chat, sender = message.get("chat"), message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict) or chat.get("type") != "private":
        return False
    chat_id, sender_id = chat.get("id"), sender.get("id")
    return type(chat_id) is int and type(sender_id) is int and chat_id > 0 and sender_id == chat_id
