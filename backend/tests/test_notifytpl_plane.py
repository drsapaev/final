"""Fail-first regression tests for the notification-template plane (group 83, #4063).

- NOTIFYTPLACTIVECLASH-BE-001: for one (notification type, channel) several
  templates can be ACTIVE at once (name is the only unique key), and the
  sender's active lookup is an unordered ``.first()`` — the content a patient
  receives may differ from the template an admin just edited.
- NOTIFYTPLRENDERFAIL-BE-001: ``CoreMixin.render_template`` catches every
  Jinja failure and returns the RAW template text; the templated sender then
  delivers that literal to patients and marks the history record ``sent`` —
  invalid templates do not fail closed.
- NOTIFYTPLPLAINTEXTESC-BE-001: the shared Jinja environment is built with
  ``autoescape=True`` and is used for EVERY channel, so HTML entities reach
  plain-text SMS bodies and the ``text/plain`` part of emails
  (``Иванов & Сын`` → ``Иванов &amp; Сын``).

Fix contract (wave 3h):
- active lookup is deterministic (newest active template wins: ordered by
  updated_at desc, id desc);
- create/update admin endpoints enforce a single-active invariant per
  (type, channel) — activating a template deactivates its siblings;
- render failures are fail-closed: nothing is sent, the history record is
  ``failed`` with the diagnostic raw content stored internally only;
- SMS and email channels render without HTML escaping; telegram keeps it
  (parse_mode=HTML), push keeps the safe default.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.crud.notification import crud_notification_template
from app.models.notification import NotificationTemplate
from app.services import notifications as notifications_module
from app.services.notifications_pkg import (
    notification_sender_service,
)

TEMPLATES_PATH = "/api/v1/notifications/templates"
TYPE = "appointment_reminder"


def _make_template(db_session, name: str, **kw) -> NotificationTemplate:
    tpl = NotificationTemplate(
        name=name,
        type=kw.get("type", TYPE),
        channel=kw.get("channel", "sms"),
        subject=kw.get("subject"),
        template=kw.get("template", "Здравствуйте, {{ patient_name }}!"),
        is_active=kw.get("is_active", True),
    )
    db_session.add(tpl)
    db_session.commit()
    db_session.refresh(tpl)
    return tpl


class TestNotifytplActiveclash:
    def test_active_template_selection_is_deterministic(self, db_session):
        """RED: unordered .first() may return the OLDER of two active
        siblings. GREEN: the lookup is deterministic — newest active wins
        (updated_at desc, id desc)."""
        older = _make_template(
            db_session, "notifytpl-clash-a", template="OLD {{ patient_name }}"
        )
        newer = _make_template(
            db_session, "notifytpl-clash-b", template="NEW {{ patient_name }}"
        )
        # make the ordering difference explicit regardless of clock granularity
        older.updated_at = datetime.now(UTC) - timedelta(seconds=30)
        newer.updated_at = datetime.now(UTC)
        db_session.commit()

        chosen = crud_notification_template.get_by_type_and_channel(
            db_session, type=TYPE, channel="sms"
        )

        assert chosen is not None
        assert chosen.id == newer.id, (
            "active lookup must deterministically pick the newest active template "
            f"(expected id={newer.id}, got id={chosen.id})"
        )

    def test_single_active_invariant_on_create(
        self, client: TestClient, admin_auth_headers
    ):
        """RED: two active templates for the same (type, channel) coexist.
        GREEN: activating the new one deactivates the previous sibling."""
        r1 = client.post(
            TEMPLATES_PATH,
            json={
                "name": "notifytpl-invariant-a",
                "type": TYPE,
                "channel": "sms",
                "template": "FIRST {{ patient_name }}",
                "is_active": True,
            },
            headers=admin_auth_headers,
        )
        assert r1.status_code in (200, 201), (r1.status_code, r1.text[:200])

        r2 = client.post(
            TEMPLATES_PATH,
            json={
                "name": "notifytpl-invariant-b",
                "type": TYPE,
                "channel": "sms",
                "template": "SECOND {{ patient_name }}",
                "is_active": True,
            },
            headers=admin_auth_headers,
        )
        assert r2.status_code in (200, 201), (r2.status_code, r2.text[:200])

        rows = client.get(TEMPLATES_PATH, headers=admin_auth_headers).json()
        siblings = [t for t in rows if t["type"] == TYPE and t["channel"] == "sms"]
        actives = [t for t in siblings if t["is_active"]]
        assert (
            len(actives) == 1
        ), "single-active invariant per (type, channel) violated: " + str(
            [(t["name"], t["is_active"]) for t in siblings]
        )
        assert actives[0]["name"] == "notifytpl-invariant-b"


class TestNotifytplRenderfail:
    @pytest.mark.asyncio
    async def test_render_failure_is_fail_closed(self, db_session, monkeypatch):
        """RED: invalid Jinja → the RAW template is sent and the history row
        is marked 'sent'. GREEN: nothing is sent, history is 'failed' and the
        raw text is not what the patient receives."""
        tpl = _make_template(
            db_session,
            "notifytpl-renderfail",
            channel="sms",
            template="{{ patient_name | nosuchfilter }}",
        )
        sms_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(
            notifications_module.notification_sender_service, "send_sms", sms_mock
        )

        history = await notification_sender_service.send_templated_notification(
            db=db_session,
            notification_type=TYPE,
            channel="sms",
            recipient_contact="+998901112233",
            template_data={"patient_name": "Иван"},
        )

        assert sms_mock.await_count == 0, "a failed render must not reach the provider"
        assert history.status == "failed", history.status
        assert "{{ patient_name | nosuchfilter }}" not in (
            history.content or ""
        ), "raw template text must not be the delivered content"
        assert history.template_id == tpl.id


class TestNotifytplPlaintextesc:
    @pytest.mark.asyncio
    async def test_sms_channel_not_html_escaped(self, db_session, monkeypatch):
        """RED: autoescape=True turns 'Иванов & Сын' into 'Иванов &amp; Сын'
        on SMS. GREEN: raw text survives on the plain-text channel."""
        _make_template(
            db_session,
            "notifytpl-esc-sms",
            channel="sms",
            template="Здравствуйте, {{ patient_name }}!",
        )
        sms_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(
            notifications_module.notification_sender_service, "send_sms", sms_mock
        )

        await notification_sender_service.send_templated_notification(
            db=db_session,
            notification_type=TYPE,
            channel="sms",
            recipient_contact="+998901112233",
            template_data={"patient_name": "Иванов & Сын"},
        )

        assert sms_mock.await_count == 1, "SMS must be attempted"
        message = (
            sms_mock.await_args.args[1]
            if sms_mock.await_args.args
            else sms_mock.await_args.kwargs["message"]
        )
        assert "Иванов & Сын" in message, message
        assert "&amp;" not in message, message

    @pytest.mark.asyncio
    async def test_email_channel_not_html_escaped(self, db_session, monkeypatch):
        """RED: the email template content lands escaped in the text/plain
        MIME part. GREEN: the plain part keeps raw text."""
        _make_template(
            db_session,
            "notifytpl-esc-email",
            channel="email",
            subject="Напоминание для {{ patient_name }}",
            template="Здравствуйте, {{ patient_name }}! Ждём вас.",
        )
        email_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(
            notifications_module.notification_sender_service, "send_email", email_mock
        )

        await notification_sender_service.send_templated_notification(
            db=db_session,
            notification_type=TYPE,
            channel="email",
            recipient_contact="patient@example.com",
            template_data={"patient_name": "Иванов & Сын"},
        )

        assert email_mock.await_count == 1, "email must be attempted"
        call = email_mock.await_args
        body = call.args[2] if len(call.args) >= 3 else call.kwargs["body"]
        assert "Иванов & Сын" in body, body
        assert "&amp;" not in body, body
