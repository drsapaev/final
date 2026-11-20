"""Sensitive verification values must not escape into 422, audit or Sentry."""

from __future__ import annotations

import json
import logging
import secrets
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exception_handlers import (
    _sanitize_validation_errors,
    register_exception_handlers,
)
from app.core.pii_masker import mask_pii
from app.core.sentry import sanitize_event
from app.middleware.audit_middleware import AuditMiddleware


class _Verification(BaseModel):
    phone: str
    code: int


class _AdminSend(BaseModel):
    phone: str
    message: str


class _ClinicalControl(BaseModel):
    code: int


@pytest.fixture
def privacy_client():
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(AuditMiddleware)

    @app.post('/api/v1/phone-verification/verify-code')
    def verify(body: _Verification):
        return {'ok': True}

    @app.post('/api/v1/phone-verification/admin/send-code')
    def admin_send(body: _AdminSend):
        return {'ok': True}

    @app.post('/api/v1/clinical/control')
    def clinical(body: _ClinicalControl):
        return {'ok': True}

    with TestClient(app) as client:
        yield client


def test_verification_invalid_input_never_echoes_in_response_or_logs(privacy_client, caplog):
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    with caplog.at_level(logging.WARNING):
        response = privacy_client.post(
            '/api/v1/phone-verification/verify-code',
            json={'phone': 'synthetic-phone', 'code': canary},
        )
    assert response.status_code == 422
    assert canary not in response.text
    assert canary not in caplog.text


def test_mounted_phone_endpoint_does_not_echo_otp(client, caplog):
    from app.api.deps import get_current_user
    from app.main import app

    canary = 'synthetic-otp-' + secrets.token_hex(6)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with caplog.at_level(logging.WARNING):
            response = client.post(
                '/api/v1/phone-verification/verify-code',
                json={'phone': '+998000000000', 'code': canary},
            )
        assert response.status_code == 422
        assert canary not in response.text
        assert canary not in caplog.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_missing_phone_does_not_echo_custom_message(privacy_client, caplog):
    canary = 'synthetic-message-' + secrets.token_hex(6)
    with caplog.at_level(logging.WARNING):
        response = privacy_client.post(
            '/api/v1/phone-verification/admin/send-code', json={'message': canary}
        )
    assert response.status_code == 422
    assert canary not in response.text
    assert canary not in caplog.text


def test_ordinary_clinical_code_validation_is_unchanged(privacy_client):
    code = 'SYNTHETIC-ICD-CONTROL'
    response = privacy_client.post('/api/v1/clinical/control', json={'code': code})
    assert response.status_code == 422
    assert response.json()['detail'][0]['input'] == code


def test_phone_audit_discards_legacy_query_but_normal_audit_keeps_diagnostics(privacy_client, caplog):
    canary = 'synthetic-message-' + secrets.token_hex(6)
    with caplog.at_level(logging.INFO, logger='app.middleware.audit_middleware'):
        privacy_client.post(
            '/api/v1/phone-verification/admin/send-code',
            params={'message': canary, 'phone': 'synthetic-phone'},
            json={'phone': 'synthetic-phone', 'message': 'ok'},
        )
        privacy_client.post('/api/v1/clinical/control?view=normal', json={'code': 1})
    audit = '\n'.join(
        record.getMessage()
        for record in caplog.records
        if record.name == 'app.middleware.audit_middleware'
    )
    assert canary not in audit
    assert 'view=normal' in audit


def test_sentry_phone_request_drops_otp_and_query():
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    event = {
        'request': {
            'method': 'POST',
            'url': 'https://synthetic.invalid/api/v1/phone-verification/verify-code?message=' + canary,
            'query_string': 'message=' + canary,
            'data': {'phone': 'synthetic-phone', 'code': canary},
        },
        'message': canary,
        'exception': {'values': [{'type': 'ValueError', 'value': canary,
                                 'stacktrace': {'frames': [{'vars': {'code': canary}}]}}]},
        'extra': {'code': canary},
        'breadcrumbs': {'values': [{'data': {'code': canary}, 'message': canary}]},
    }
    safe = sanitize_event(event)
    assert canary not in json.dumps(safe)
    assert safe['exception'] == {'values': [{'type': 'ValueError'}]}


def test_sentry_drops_sensitive_http_breadcrumb_but_keeps_unrelated_code():
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    event = {'breadcrumbs': {'values': [{'data': {
        'url': '/api/v1/phone-verification/verify-code', 'code': canary,
    }, 'message': canary}]}, 'extra': {'code': 'ICD-CONTROL'}}
    safe = sanitize_event(event)
    assert canary not in json.dumps(safe)
    assert safe['extra']['code'] == 'ICD-CONTROL'


def test_installed_sentry_before_send_uses_sensitive_route_scrub(monkeypatch):
    from app.core import sentry

    sdk = ModuleType('sentry_sdk')
    sdk.__path__ = []
    sdk.init = Mock()
    integrations = ModuleType('sentry_sdk.integrations')
    integrations.__path__ = []
    monkeypatch.setitem(sys.modules, 'sentry_sdk', sdk)
    monkeypatch.setitem(sys.modules, 'sentry_sdk.integrations', integrations)
    for module_name, name in (
        ('fastapi', 'FastApiIntegration'), ('redis', 'RedisIntegration'),
        ('sqlalchemy', 'SqlalchemyIntegration'), ('asyncpg', 'AsyncPGIntegration'),
    ):
        module = ModuleType(f'sentry_sdk.integrations.{module_name}')
        setattr(module, name, lambda: object())
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.delenv('TESTING', raising=False)
    monkeypatch.setenv('SENTRY_DSN', 'enabled')
    sentry.init_sentry()
    callback = sdk.init.call_args.kwargs['before_send']
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    event = {'request': {'method': 'POST', 'url': '/api/v1/phone-verification/verify-code',
                         'data': {'code': canary}},
             'message': canary, 'extra': {'code': canary},
             'exception': {'values': [{'type': 'ValueError', 'value': canary}]}}
    safe = callback(event, {})
    assert safe is not None
    assert canary not in json.dumps(safe)
    assert safe.get('transaction') == '[REDACTED TRANSACTION]'


def test_named_verification_secrets_are_redacted_without_redacting_generic_code():
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    assert mask_pii({'verification_code': canary})['verification_code'] == '[REDACTED]'
    assert canary not in mask_pii(json.dumps({'verification_code': canary}))
    assert mask_pii({'code': 'ICD-CONTROL'})['code'] == 'ICD-CONTROL'
    assert mask_pii('hotpot%3Dcontrol') == 'hotpot%3Dcontrol'
    assert canary not in mask_pii('verification%5Fcode=' + canary)
    assert canary not in mask_pii('verification%2Dcode=' + canary)
    assert canary not in mask_pii("Request(verification_code='" + canary + "')")
    assert mask_pii({'verification-code': canary})['verification-code'] == '[REDACTED]'


def test_named_secret_validation_error_scrubs_validator_message_and_context():
    canary = 'synthetic-otp-' + secrets.token_hex(6)
    result = _sanitize_validation_errors([
        {'loc': ('body', 'verificationCode'), 'input': canary,
         'msg': 'invalid ' + canary, 'ctx': {'error': canary}},
        {'loc': ('body', 'verification_code'), 'msg': canary, 'ctx': {'error': canary}},
    ])
    assert canary not in json.dumps(result)
