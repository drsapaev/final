"""SMTP-отправка не должна блокировать event loop и обязана иметь таймаут.

Review follow-up to #2802 (P1): send_email_enhanced выполнял синхронный
smtplib (connect/TLS/login/send) прямо в async-коде без таймаута —
медленный или недоступный SMTP-сервер подвешивал весь event loop FastAPI.
"""
from __future__ import annotations

import smtplib
import threading

import pytest

from app.services.email_sms_enhanced import EmailSMSEnhancedService


class _RecordingSMTP:
    instances: list["_RecordingSMTP"] = []

    def __init__(self, server, port, timeout=None):
        self.timeout = timeout
        self.thread = threading.current_thread()
        _RecordingSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        pass


@pytest.fixture(autouse=True)
def _reset_instances():
    _RecordingSMTP.instances = []


def _svc(monkeypatch) -> EmailSMSEnhancedService:
    svc = EmailSMSEnhancedService()
    svc.smtp_username = "u"
    svc.smtp_password = "p"
    svc.smtp_server = "smtp.test.local"
    svc.smtp_port = 587
    svc.smtp_use_tls = True
    monkeypatch.setattr(smtplib, "SMTP", _RecordingSMTP)
    return svc


@pytest.mark.asyncio
async def test_smtp_connection_has_timeout(monkeypatch):
    svc = _svc(monkeypatch)

    ok, _ = await svc.send_email_enhanced(
        to_email="a@b.test", subject="s", text_content="body"
    )

    assert ok is True
    assert _RecordingSMTP.instances[0].timeout == 30


@pytest.mark.asyncio
async def test_smtp_runs_off_event_loop_thread(monkeypatch):
    svc = _svc(monkeypatch)

    ok, _ = await svc.send_email_enhanced(
        to_email="a@b.test", subject="s", text_content="body"
    )

    assert ok is True
    worker_thread = _RecordingSMTP.instances[0].thread
    assert worker_thread is not threading.main_thread()
