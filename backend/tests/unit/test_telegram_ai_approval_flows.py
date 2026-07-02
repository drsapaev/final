import json
from uuid import uuid4

import pytest

from app.api.v1.endpoints import admin_telegram
from app.models.audit import AuditLog
from app.models.telegram_config import TelegramUser


class _FakeTelegramBot:
    active = True
    bot_token = "test-token"

    def __init__(self):
        self.sent = []

    async def initialize(self, db):
        return True

    async def _send_message(self, chat_id, text, reply_markup=None):
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return True


def test_ai_approval_message_uses_protected_link_and_ignores_medical_context():
    message = admin_telegram.build_telegram_ai_approval_message(
        "doctor_draft_review",
        "https://clinic.example/doctor?tab=ai",
        {
            "draft_count": 1,
            "diagnosis": "Raw diagnosis must not leak",
            "complaints": "Full EMR complaint text must not leak",
            "patient_name": "Patient Name",
        },
    )

    assert message["contains_plain_chat_medical_content"] is False
    assert message["autonomous_mutation_allowed"] is False
    assert message["requires_human_confirmation"] is True
    assert message["safe_metric_keys"] == ["draft_count"]
    assert "Raw diagnosis" not in message["text"]
    assert "Full EMR" not in message["text"]
    assert "Patient Name" not in message["text"]
    assert (
        message["reply_markup"]["inline_keyboard"][0][0]["url"]
        == "https://clinic.example/doctor?tab=ai"
    )


def test_ai_approval_contract_blocks_autonomous_mutation():
    status = admin_telegram._build_telegram_ai_approval_status()

    assert status["notification_runtime_enabled"] is True
    assert status["outcome_capture_enabled"] is True
    assert status["plain_chat_medical_content_allowed"] is False
    assert status["autonomous_mutation_allowed"] is False
    assert status["domain_mutations_performed_by_telegram_ai"] is False
    assert all(
        workflow["plain_chat_medical_content_allowed"] is False
        and workflow["autonomous_mutation_allowed"] is False
        for workflow in status["workflows"]
    )


@pytest.mark.asyncio
async def test_ai_approval_alert_sends_safe_staff_message_and_audit(
    db_session, admin_user, test_doctor_user, monkeypatch
):
    chat_id = 720000 + test_doctor_user.id
    db_session.add(
        TelegramUser(
            user_id=test_doctor_user.id,
            chat_id=chat_id,
            username=f"doctor_{uuid4().hex[:8]}",
            language_code="ru",
            active=True,
            blocked=False,
            notifications_enabled=True,
        )
    )
    db_session.flush()
    fake_bot = _FakeTelegramBot()

    async def _fake_get_telegram_bot_service():
        return fake_bot

    monkeypatch.setattr(admin_telegram.settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(
        admin_telegram,
        "get_telegram_bot_service",
        _fake_get_telegram_bot_service,
    )

    result = await admin_telegram.send_telegram_ai_approval_alert(
        admin_telegram.TelegramAiApprovalAlertRequest(
            workflow_key="doctor_draft_review",
            recipient_user_id=test_doctor_user.id,
            target_reference="visit:123:patient:456",
            metrics={
                "draft_count": 1,
                "diagnosis": "Sensitive diagnosis",
                "emr_text": "Full EMR text",
            },
        ),
        db_session,
        admin_user,
    )

    assert result["success"] is True
    assert result["plain_chat_medical_content_allowed"] is False
    assert fake_bot.sent[0]["chat_id"] == chat_id
    assert "Sensitive diagnosis" not in fake_bot.sent[0]["text"]
    assert "Full EMR text" not in fake_bot.sent[0]["text"]
    assert fake_bot.sent[0]["reply_markup"]["inline_keyboard"][0][0]["url"] == (
        "https://clinic.example/doctor?tab=ai"
    )

    audit_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "telegram_ai_approval_notification_sent")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_log is not None
    payload_text = json.dumps(audit_log.payload, sort_keys=True)
    assert "visit:123" not in payload_text
    assert "patient:456" not in payload_text
    assert audit_log.payload["target_reference_hash"].startswith(
        "telegram_ai_approval:"
    )
    assert audit_log.payload["domain_mutation"] is False


def test_ai_approval_outcome_records_hash_only_without_domain_mutation(
    db_session, test_doctor_user, admin_user
):
    doctor_result = admin_telegram.capture_telegram_ai_approval_outcome(
        admin_telegram.TelegramAiApprovalOutcomeRequest(
            workflow_key="doctor_draft_review",
            outcome="accepted",
            target_reference="visit:123:patient:456",
            reason_code="accurate",
        ),
        db_session,
        test_doctor_user,
    )
    admin_result = admin_telegram.capture_telegram_ai_approval_outcome(
        admin_telegram.TelegramAiApprovalOutcomeRequest(
            workflow_key="queue_overload_alert",
            outcome="rejected",
            target_reference="queue:raw:789",
            reason_code="free text that may contain sensitive details",
        ),
        db_session,
        admin_user,
    )

    assert doctor_result["outcome"] == "accepted"
    assert admin_result["outcome"] == "rejected"
    assert admin_result["reason_code"] == "other"
    assert doctor_result["domain_mutation"] is False
    assert admin_result["autonomous_mutation_allowed"] is False

    logs = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "telegram_ai_approval_outcome_recorded")
        .order_by(AuditLog.id.desc())
        .all()
    )
    assert len(logs) >= 2
    payload_text = json.dumps([log.payload for log in logs[:2]], sort_keys=True)
    assert "visit:123" not in payload_text
    assert "patient:456" not in payload_text
    assert "queue:raw:789" not in payload_text
    assert "free text" not in payload_text
    assert all(log.payload["domain_mutation"] is False for log in logs[:2])
