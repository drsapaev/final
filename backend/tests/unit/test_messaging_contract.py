from __future__ import annotations

from app.core.messaging_contract import (
    CONTRACT_VERSION,
    MessageEventType,
    build_ws_event_payload,
    is_ephemeral_message_event,
    is_reliable_message_event,
    is_supported_contract_version,
)


def test_new_message_payload_is_wrapped_consistently():
    payload = build_ws_event_payload(
        MessageEventType.NEW_MESSAGE,
        {"id": 7, "content": "Привет"},
    )

    assert payload == {
        "type": "new_message",
        "contract_version": "2026-03",
        "message": {
            "id": 7,
            "content": "Привет",
        },
    }


def test_all_events_carry_contract_version():
    payload = build_ws_event_payload(MessageEventType.PING)

    assert payload == {
        "type": "ping",
        "contract_version": CONTRACT_VERSION,
    }


def test_supported_contract_version_helper_accepts_missing_and_current_version():
    assert is_supported_contract_version(None)
    assert is_supported_contract_version(CONTRACT_VERSION)
    assert not is_supported_contract_version("2026-04")


def test_contract_distinguishes_reliable_and_ephemeral_events():
    assert is_reliable_message_event(MessageEventType.NEW_MESSAGE)
    assert is_reliable_message_event(MessageEventType.MESSAGE_READ)
    assert not is_reliable_message_event(MessageEventType.TYPING)

    assert is_ephemeral_message_event(MessageEventType.TYPING)
    assert is_ephemeral_message_event(MessageEventType.GET_ONLINE_STATUS)
    assert not is_ephemeral_message_event(MessageEventType.NEW_MESSAGE)
