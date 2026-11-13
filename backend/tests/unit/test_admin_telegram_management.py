from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.admin_telegram._management import (
    get_telegram_stats,
    get_telegram_users,
    send_broadcast_message,
)
from app.models.telegram_config import TelegramMessage, TelegramUser


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
    db_session.add_all(
        [
            TelegramUser(chat_id=100001, last_activity=now, first_name="Synthetic"),
            TelegramUser(
                chat_id=100002,
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

    assert result["total_users"] == 2
    assert result["active_users"] == 1
    assert result["messages_sent"] == 2
    assert result["messages_delivered"] == 1
    assert result["messages_failed"] == 1
    assert result["by_message_type"] == {
        "patient_bot_reply": 2,
        "lab_result_pdf": 1,
    }


@pytest.mark.unit
def test_telegram_users_returns_paged_masked_records(db_session, admin_user):
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all(
        [
            TelegramUser(
                chat_id=123456789,
                first_name="Synthetic",
                last_name="Patient",
                last_activity=now,
            ),
            TelegramUser(
                chat_id=987654321,
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

    assert result["total"] == 1
    assert len(result["users"]) == 1
    assert result["users"][0]["name_initials"] == "S.P."
    assert result["users"][0]["chat_id_suffix"] == "6789"
    assert "first_name" not in result["users"][0]
    assert "chat_id" not in result["users"][0]


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
