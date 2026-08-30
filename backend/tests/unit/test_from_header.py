"""Канонический заголовок From для email-отправителей.

Review follow-up to #2799 (два P1):
1. SMTP_FROM игнорировался в NotificationSenderService — канал ставил
   From = SMTP-логин, и провайдер мог отклонять/перезаписывать письма.
2. SMTP_FROM в документированном формате «Name <mailbox>» получал вторую
   обёртку «Programma Clinic <Name <mailbox>>» — парсер адресов даёт
   пустой envelope-sender.
"""
from __future__ import annotations

import smtplib

import pytest

from app.services.email_sms_enhanced import (
    EmailSMSEnhancedService,
    build_from_header,
)
from app.services.notifications import NotificationSenderService


def test_bare_mailbox_gets_wrapped():
    assert (
        build_from_header("no-reply@finalclinic.fyi")
        == "Programma Clinic <no-reply@finalclinic.fyi>"
    )


def test_full_header_is_used_as_is():
    value = "Clinic System <noreply@example.com>"
    assert build_from_header(value) == value


def test_sender_missing_falls_back_to_username():
    assert (
        build_from_header(None, "login@brevo.example")
        == "Programma Clinic <login@brevo.example>"
    )


class _CapturingSMTP:
    sent: list = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        _CapturingSMTP.sent.append(msg)

    def quit(self):
        pass


@pytest.fixture(autouse=True)
def _reset():
    _CapturingSMTP.sent = []


def _enhanced_svc(monkeypatch, smtp_from=None):
    svc = EmailSMSEnhancedService()
    svc.smtp_username = "login@brevo.example"
    svc.smtp_password = "p"
    svc.smtp_server = "smtp.test.local"
    svc.smtp_port = 587
    svc.smtp_use_tls = False
    svc.smtp_from = smtp_from
    monkeypatch.setattr(smtplib, "SMTP", _CapturingSMTP)
    return svc


@pytest.mark.asyncio
async def test_send_email_enhanced_uses_smtp_from(monkeypatch):
    svc = _enhanced_svc(monkeypatch, smtp_from="no-reply@finalclinic.fyi")

    ok, _ = await svc.send_email_enhanced(
        to_email="a@b.test", subject="s", text_content="body"
    )

    assert ok is True
    assert (
        _CapturingSMTP.sent[0]["From"] == "Programma Clinic <no-reply@finalclinic.fyi>"
    )


@pytest.mark.asyncio
async def test_send_email_enhanced_accepts_full_header_format(monkeypatch):
    full = "Clinic System <noreply@example.com>"
    svc = _enhanced_svc(monkeypatch, smtp_from=full)

    ok, _ = await svc.send_email_enhanced(
        to_email="a@b.test", subject="s", text_content="body"
    )

    assert ok is True
    assert _CapturingSMTP.sent[0]["From"] == full


def _notification_channel(monkeypatch, smtp_from=None):
    """Канал уведомлений без полного __init__ (только SMTP-атрибуты)."""
    svc = object.__new__(NotificationSenderService)
    svc.smtp_server = "smtp.test.local"
    svc.smtp_port = 587
    svc.smtp_username = "login@brevo.example"
    svc.smtp_password = "p"
    svc.smtp_from = smtp_from
    monkeypatch.setattr(smtplib, "SMTP", _CapturingSMTP)
    return svc


def test_notification_channel_uses_smtp_from(monkeypatch):
    svc = _notification_channel(monkeypatch, smtp_from="no-reply@finalclinic.fyi")

    ok = svc._send_email_sync("a@b.test", "s", "body")

    assert ok is True
    assert (
        _CapturingSMTP.sent[0]["From"] == "Programma Clinic <no-reply@finalclinic.fyi>"
    )


def test_notification_channel_defaults_to_login_without_smtp_from(monkeypatch):
    svc = _notification_channel(monkeypatch, smtp_from=None)

    ok = svc._send_email_sync("a@b.test", "s", "body")

    assert ok is True
    assert (
        _CapturingSMTP.sent[0]["From"] == "Programma Clinic <login@brevo.example>"
    )
