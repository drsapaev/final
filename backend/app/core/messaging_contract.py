"""Canonical messaging contract shared across the chat stack."""

from __future__ import annotations

from enum import Enum
from typing import Any


class MessageEventType(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    NEW_MESSAGE = "new_message"
    MESSAGE_READ = "message_read"
    MESSAGES_READ = "messages_read"
    REACTION_UPDATE = "reaction_update"
    MESSAGE_DELETED = "message_deleted"
    TYPING = "typing"
    GET_ONLINE_STATUS = "get_online_status"
    ONLINE_STATUS = "online_status"
    PING = "ping"
    PONG = "pong"


MESSAGE_STATUSES = (
    "pending",
    "sent",
    "delivered",
    "read",
    "failed",
)

ATTACHMENT_STATUSES = (
    "uploading",
    "uploaded",
    "scanned",
    "available",
    "blocked",
)

AI_CHAT_STATUSES = (
    "draft",
    "streaming",
    "completed",
    "failed",
    "cancelled",
)

RELIABLE_MESSAGE_EVENTS = frozenset(
    {
        MessageEventType.NEW_MESSAGE.value,
        MessageEventType.MESSAGE_READ.value,
        MessageEventType.MESSAGES_READ.value,
        MessageEventType.REACTION_UPDATE.value,
        MessageEventType.MESSAGE_DELETED.value,
    }
)

EPHEMERAL_MESSAGE_EVENTS = frozenset(
    {
        MessageEventType.TYPING.value,
        MessageEventType.GET_ONLINE_STATUS.value,
        MessageEventType.ONLINE_STATUS.value,
        MessageEventType.PING.value,
        MessageEventType.PONG.value,
    }
)

CONTRACT_VERSION = "2026-03"


def normalize_event_type(event_type: MessageEventType | str) -> str:
    if isinstance(event_type, MessageEventType):
        return event_type.value
    return str(event_type)


def build_ws_event_payload(event_type: MessageEventType | str, data: Any | None = None) -> dict[str, Any]:
    normalized_event_type = normalize_event_type(event_type)
    payload: dict[str, Any] = {
        "type": normalized_event_type,
        "contract_version": CONTRACT_VERSION,
    }
    if isinstance(data, dict):
        if normalized_event_type == MessageEventType.NEW_MESSAGE.value and "message" not in data:
            payload["message"] = data
        else:
            payload.update(data)
    elif data is not None:
        payload["data"] = data
    return payload


def is_reliable_message_event(event_type: MessageEventType | str) -> bool:
    return normalize_event_type(event_type) in RELIABLE_MESSAGE_EVENTS


def is_ephemeral_message_event(event_type: MessageEventType | str) -> bool:
    return normalize_event_type(event_type) in EPHEMERAL_MESSAGE_EVENTS


def is_supported_contract_version(contract_version: str | None) -> bool:
    return contract_version in (None, CONTRACT_VERSION)
