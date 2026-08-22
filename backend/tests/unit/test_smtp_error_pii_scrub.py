"""Provider exception text must be scrubbed of recipient PII.

Review follow-up to #2802 (P1): smtplib exceptions (e.g.
SMTPRecipientsRefused) quote the recipient address. The email service
logged str(e) verbatim and returned it to callers, and the password-reset
endpoint echoed it into the HTTP 502 detail — a PII leak to logs, Sentry,
and the client. Fixed by masking at the email-service boundary plus a
generic client-facing error in the password-reset service.
"""
from __future__ import annotations

import logging
import smtplib

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.password_reset_service import get_password_reset_service

RECIPIENT = "drsapaev@gmail.com"
MASKED_LOCAL = "d" + "•••" + "@gmail.com"


class _RefusingSMTP:
    """smtplib.SMTP stand-in that refuses the recipient."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        raise smtplib.SMTPRecipientsRefused({RECIPIENT: (550, b"User unknown")})

    def __exit__(self, *exc):
        return False


def _configured_service(monkeypatch) -> EmailSMSEnhancedService:
    svc = EmailSMSEnhancedService()
    svc.smtp_username = "smtp-user"
    svc.smtp_password = "smtp-pass"
    svc.smtp_server = "smtp.test.local"
    svc.smtp_port = 587
    svc.smtp_use_tls = False
    monkeypatch.setattr(smtplib, "SMTP", _RefusingSMTP)
    return svc


@pytest.fixture
def scrub_user(db_session):
    user = User(
        username="smtp_scrub_user",
        email=RECIPIENT,
        full_name="SMTP Scrub User",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_send_email_failure_returns_masked_error(monkeypatch):
    svc = _configured_service(monkeypatch)

    ok, message = await svc.send_email_enhanced(
        to_email=RECIPIENT, subject="test", text_content="body"
    )

    assert ok is False
    assert RECIPIENT not in message
    assert MASKED_LOCAL in message


@pytest.mark.asyncio
async def test_send_email_failure_does_not_log_recipient(monkeypatch, caplog):
    svc = _configured_service(monkeypatch)

    with caplog.at_level(logging.ERROR):
        await svc.send_email_enhanced(
            to_email=RECIPIENT, subject="test", text_content="body"
        )

    assert "drsapaev" not in caplog.text
    assert MASKED_LOCAL in caplog.text


@pytest.mark.asyncio
async def test_password_reset_send_failure_is_generic_to_client(
    db_session, scrub_user, monkeypatch, caplog
):
    svc = get_password_reset_service()
    svc.reset_tokens = {}

    async def refusing_send(to_email, subject, **kwargs):
        # Намеренно «грязный» текст — как будто маскировка не сработала
        # ниже по цепочке: password-reset обязан защищаться сам.
        return False, repr(
            smtplib.SMTPRecipientsRefused({RECIPIENT: (550, b"User unknown")})
        )

    monkeypatch.setattr(svc.email_service, "send_email_enhanced", refusing_send)

    with caplog.at_level(logging.WARNING):
        result = await svc.initiate_email_reset(db_session, email=scrub_user.email)

    # Анти-enumeration (#2800 follow-up): сбой доставки неотличим от
    # успеха и от неизвестного адреса — единая форма ответа.
    assert result["success"] is True
    assert result["message"] == (
        "Если пользователь с таким email существует, "
        "ссылка для сброса отправлена"
    )
    assert "error" not in result and "error_code" not in result
    # Сервер логирует причину замаскированной
    assert "drsapaev" not in caplog.text
    assert MASKED_LOCAL in caplog.text
