from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.admin_telegram._management import (
    get_telegram_stats,
    get_telegram_users,
    send_broadcast_message,
)
from app.main import app
from app.models.telegram_config import TelegramMessage, TelegramUser


def _unique_chat_id(db_session) -> int:
    existing_ids = {
        int(chat_id)
        for (chat_id,) in db_session.query(TelegramUser.chat_id).all()
        if chat_id is not None
    }
    existing_suffixes = {str(chat_id)[-4:] for chat_id in existing_ids}
    while True:
        candidate = 1_000_000_000_000_000 + uuid4().int % 1_000_000_000_000_000
        if (
            candidate not in existing_ids
            and str(candidate)[-4:] not in existing_suffixes
        ):
            return candidate


def _message(
    *,
    created_at: datetime,
    message_type: str,
    status: str = "sent",
) -> TelegramMessage:
    return TelegramMessage(
        chat_id=100001,
        message_type=message_type,
        message_text="Synthetic test message",
        status=status,
        created_at=created_at,
    )


@pytest.mark.unit
def test_telegram_stats_uses_registered_users_and_message_log(db_session, admin_user):
    now = datetime.now(UTC).replace(tzinfo=None)
    before = get_telegram_stats(days_back=7, db=db_session, current_user=admin_user)
    db_session.add_all(
        [
            TelegramUser(
                chat_id=_unique_chat_id(db_session),
                last_activity=now,
                first_name="Synthetic",
            ),
            TelegramUser(
                chat_id=_unique_chat_id(db_session),
                last_activity=now - timedelta(days=30),
                active=False,
            ),
            _message(
                created_at=now - timedelta(days=1),
                message_type="patient_bot_reply",
                status="sent",
            ),
            _message(
                created_at=now - timedelta(days=2),
                message_type="lab_result_pdf",
                status="delivered",
            ),
            _message(
                created_at=now - timedelta(days=3),
                message_type="patient_bot_reply",
                status="failed",
            ),
            _message(
                created_at=now - timedelta(days=30),
                message_type="old_message",
            ),
        ]
    )
    db_session.flush()

    result = get_telegram_stats(days_back=7, db=db_session, current_user=admin_user)

    assert result["total_users"] == before["total_users"] + 2
    assert result["active_users"] == before["active_users"] + 1
    assert result["messages_sent"] == before["messages_sent"] + 2
    assert result["messages_delivered"] == before["messages_delivered"] + 1
    assert result["messages_failed"] == before["messages_failed"] + 1
    assert result["by_message_type"]["patient_bot_reply"] == (
        before["by_message_type"].get("patient_bot_reply", 0) + 2
    )
    assert result["by_message_type"]["lab_result_pdf"] == (
        before["by_message_type"].get("lab_result_pdf", 0) + 1
    )


@pytest.mark.unit
def test_telegram_users_returns_paged_masked_records(db_session, admin_user):
    now = datetime.now(UTC).replace(tzinfo=None)
    before = get_telegram_users(
        skip=0,
        limit=500,
        active_only=True,
        db=db_session,
        current_user=admin_user,
    )
    chat_id = _unique_chat_id(db_session)
    db_session.add_all(
        [
            TelegramUser(
                chat_id=chat_id,
                first_name="Synthetic",
                last_name="Patient",
                last_activity=datetime.max,
            ),
            TelegramUser(
                chat_id=_unique_chat_id(db_session),
                first_name="Inactive",
                last_activity=now - timedelta(days=5),
                active=False,
            ),
        ]
    )
    db_session.flush()

    result = get_telegram_users(
        skip=0,
        limit=10,
        active_only=True,
        db=db_session,
        current_user=admin_user,
    )

    assert result["total"] == before["total"] + 1
    user = next(
        item for item in result["users"] if item["chat_id_suffix"] == str(chat_id)[-4:]
    )
    assert user["name_initials"] == "S.P."
    assert "first_name" not in user
    assert "chat_id" not in user


@pytest.mark.unit
def test_telegram_broadcast_does_not_claim_queued_success(admin_user):
    with pytest.raises(HTTPException) as exc_info:
        send_broadcast_message(
            message="Synthetic announcement",
            target_groups=["patients"],
            language="ru",
            current_user=admin_user,
        )

    assert exc_info.value.status_code == 501
    assert "no messages were sent" in exc_info.value.detail


@pytest.mark.unit
def test_telegram_broadcast_openapi_documents_only_disabled_response():
    operation = app.openapi()["paths"]["/api/v1/admin/telegram/broadcast"]["post"]

    assert "200" not in operation["responses"]
    assert "501" in operation["responses"]
    response = operation["responses"]["501"]
    assert response["description"] == "Telegram broadcast delivery is disabled."
    json_response = response["content"]["application/json"]
    assert json_response["schema"] == {
        "type": "object",
        "properties": {"detail": {"type": "string"}},
        "required": ["detail"],
    }
    assert json_response["example"] == {
        "detail": "Telegram broadcast delivery is not configured; no messages were sent."
    }
