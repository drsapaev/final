"""DOCINVITE-BE-002 (audit #3892, group 20) — phone invitation must create a
durable, retrievable registrar task bound to the visit.

Audit snapshot: the phone invitation helper only logged and always returned
``success: true`` / "Создана задача для регистратуры", and the schedule-next
response mapped that into ``confirmation.notification_sent`` — a false claim.
The durable protected-inbox rewrite landed in #4060 (commit ``2329735d4``):
``_send_phone_invitation`` now fans out a canonical
``appointment_confirmation_task`` notification to the registrar role bound to
the visit (entity_type=visit / entity_id=visit_id), and the doctor
schedule-next endpoint maps ``notification_sent`` from the real persistence
result. No test pinned that contract — this file is the audit-required
synthetic regression pin (GREEN-on-main; the fix itself predates it).

Run: pytest backend/tests/unit/test_docinvite_phone_task.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notifications_pkg import NotificationSenderService


@pytest.mark.unit
class TestDocInvitePhoneTask:
    def test_phone_invitation_persists_registrar_task_bound_to_visit(
        self, db_session, test_patient, test_visit, registrar_user
    ):
        """Schedule-path on the phone channel must leave a persistent,
        retrievable work item bound to the visit for the registrar team —
        not just a log line."""
        service = NotificationSenderService()
        result = asyncio.run(
            service._send_phone_invitation(
                test_patient, {"visit_id": test_visit.id}, db=db_session
            )
        )

        assert result["success"] is True, result
        assert result["channel"] == "phone"
        assert "Создана задача" in result["message"]

        event = (
            db_session.query(NotificationEvent)
            .filter(
                NotificationEvent.event_type == "appointment_confirmation_task",
                NotificationEvent.entity_type == "visit",
                NotificationEvent.entity_id == str(test_visit.id),
            )
            .first()
        )
        assert event is not None, "registrar task must be persisted and bound to the visit"

        delivery = (
            db_session.query(NotificationDelivery)
            .filter(
                NotificationDelivery.event_id == event.id,
                NotificationDelivery.recipient_id == registrar_user.id,
                NotificationDelivery.recipient_type == "user",
                NotificationDelivery.role == "registrar",
            )
            .first()
        )
        assert delivery is not None, "registrar must have a retrievable inbox item"

    def test_no_registrars_is_honest_false(self, db_session, test_patient, test_visit):
        """Without any registrar user to receive the task, the helper must
        report failure (the schedule-next mapping then yields
        notification_sent=false) — never a fabricated success."""
        service = NotificationSenderService()
        result = asyncio.run(
            service._send_phone_invitation(
                test_patient, {"visit_id": test_visit.id}, db=db_session
            )
        )

        assert result["success"] is False
        assert "Не удалось" in (result.get("message") or result.get("error", ""))
        assert db_session.query(NotificationEvent).filter(
            NotificationEvent.event_type == "appointment_confirmation_task"
        ).first() is None

    def test_missing_db_never_claims_success(self, test_patient, test_visit):
        """db=None must fail honestly without claiming a task was created."""
        service = NotificationSenderService()
        result = asyncio.run(
            service._send_phone_invitation(
                test_patient, {"visit_id": test_visit.id}, db=None
            )
        )

        assert result["success"] is False
        assert "Не удалось" in (result.get("message") or result.get("error", ""))
