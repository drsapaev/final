"""LABN-FE-001 (audit 3886 round 10) — instance-scoped lab report Telegram
notification contract.

Fail-first contract evidence: the pre-fix frontend request shape
``POST /telegram/send-lab-results`` with a JSON body
``{patient_id, instance_id}`` is rejected by the actual registered route
with 422 before any business logic — the legacy route validates
``patient_id``/``lab_result_ids`` as query parameters against the legacy
lab_result storage, and no payload mapping can turn an instance ID into
legacy result IDs.

The new dedicated route ``POST /telegram/send-lab-report-instance`` takes
an explicit body model ``{patient_id, report_instance_id}``, enforces
patient binding, doctor scope, FINALIZED/PRINTED status and Telegram
consent server-side, renders the same PDF as the download endpoint and
delivers it through the bot's sendDocument path. 200 + ``success:false``
means the patient did NOT receive the report (not linked / notifications
disabled) — the frontend must show that as a failure (LABN-FE-002).

All bot/PDF/DB dependencies are mocked; no real Telegram calls, no real
patient data (synthetic identities only).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import telegram_notifications
from app.api.v1.endpoints.telegram_notifications import router as telegram_router

# ---------------------------------------------------------------------------
# Minimal FastAPI app with the REAL registered router (route validation
# contract), auth/db dependencies overridden with synthetic in-memory ones.
# ---------------------------------------------------------------------------

SYNTHETIC_ADMIN = SimpleNamespace(
    id=1,
    role="Admin",
    is_superuser=False,
    is_active=True,
    username="synthetic-admin",
)


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(telegram_router, prefix="/telegram")
    app.dependency_overrides[get_current_user] = lambda: SYNTHETIC_ADMIN
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return _build_client()


def _synthetic_instance(
    *,
    instance_id: int = 91,
    patient_id: int = 444,
    status: str = "FINALIZED",
):
    return SimpleNamespace(
        id=instance_id,
        patient_id=patient_id,
        status=status,
        visit_id=555,
        finalized_at=None,
        created_at=None,
        branding_snapshot={},
        patient_snapshot={"patient_id": patient_id, "full_name": "SYNTHETIC Пациент"},
        signer_snapshot={},
        template=SimpleNamespace(name="ОАК"),
        template_version=SimpleNamespace(
            layout_preset="a4",
            page_settings={},
            footer_notes=None,
        ),
    )


def _patch_success_flow(monkeypatch, *, instance=None, patient=None, telegram_user=None):
    """Patch every external dependency of the happy path; return the send mock."""
    instance = instance or _synthetic_instance()
    patient = patient or SimpleNamespace(phone="+998901234567")
    telegram_user = telegram_user or SimpleNamespace(
        chat_id=998877,
        language_code="ru",
        notifications_enabled=True,
        lab_notifications=True,
    )

    service = SimpleNamespace(
        get_instance=Mock(return_value=instance),
        materialize_instance=Mock(return_value=[{"key": "cbc", "fields": []}]),
        summarize_critical_findings=Mock(return_value=[]),
    )
    pdf_service = SimpleNamespace(render_report=Mock(return_value=b"%PDF-synthetic"))

    bot_service = SimpleNamespace(
        active=True,
        initialize=AsyncMock(),
        _send_document=AsyncMock(return_value=(True, 4242, None)),
    )

    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _pid: patient,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: telegram_user,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.lab_reporting.LabReportingService",
        lambda _db: service,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.lab_report_pdf_service.lab_report_pdf_service",
        pdf_service,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications,
        "get_telegram_bot_service",
        AsyncMock(return_value=bot_service),
        raising=False,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.telegram_webhook._helpers._ensure_bot_service_fresh",
        AsyncMock(),
        raising=False,
    )
    return bot_service, pdf_service, service


# ---------------------------------------------------------------------------
# LABN-FE-001 fail-first contract: the OLD frontend request shape.
# ---------------------------------------------------------------------------


class TestLegacyRouteRejectsOldFrontendShape:
    def test_old_frontend_body_shape_is_rejected_422_before_business_logic(self, client):
        """The exact pre-fix frontend request: JSON body with instance_id."""
        response = client.post(
            "/telegram/send-lab-results",
            json={"patient_id": 444, "instance_id": 91},
        )
        assert response.status_code == 422, (
            "the legacy route must reject the old frontend JSON body at "
            "validation (patient_id/lab_result_ids are query parameters) — "
            "this is the LABN-FE-001 contract break"
        )


# ---------------------------------------------------------------------------
# New route: validation contract.
# ---------------------------------------------------------------------------


class TestNewRouteValidationContract:
    def test_missing_body_is_rejected_422(self, client):
        response = client.post("/telegram/send-lab-report-instance")
        assert response.status_code == 422

    def test_legacy_instance_id_field_name_is_rejected_422(self, client):
        """A wrong-shape request (the legacy field name) must fail readable
        validation instead of silently mapping unrelated ID spaces."""
        response = client.post(
            "/telegram/send-lab-report-instance",
            json={"patient_id": 444, "instance_id": 91},
        )
        assert response.status_code == 422
        body = response.json()
        assert any("report_instance_id" in str(err.get("loc", [])) for err in body["detail"])

    def test_legacy_lab_result_ids_shape_is_rejected_422(self, client):
        response = client.post(
            "/telegram/send-lab-report-instance",
            json={"patient_id": 444, "lab_result_ids": [1, 2]},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# New route: behavior (direct handler invocation, module deps mocked).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_delivers_finalized_pdf_document(monkeypatch):
    bot_service, pdf_service, service = _patch_success_flow(monkeypatch)
    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    result = await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)

    assert result["success"] is True
    assert result["report_instance_id"] == 91
    # The delivered document is the rendered report PDF for THIS instance.
    pdf_service.render_report.assert_called_once()
    render_payload = pdf_service.render_report.call_args[0][0]
    assert render_payload["template_name"] == "ОАК"
    bot_service._send_document.assert_awaited_once()
    send_kwargs = bot_service._send_document.call_args.kwargs
    assert send_kwargs["chat_id"] == 998877
    assert send_kwargs["filename"] == "lab-report-91.pdf"
    assert send_kwargs["document_bytes"] == b"%PDF-synthetic"
    service.get_instance.assert_called_once_with(91)


@pytest.mark.asyncio
async def test_patient_not_found_is_404(monkeypatch):
    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _pid: None,
        raising=False,
    )
    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=404, report_instance_id=91
    )

    with pytest.raises(Exception) as excinfo:
        await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)
    assert getattr(excinfo.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_unlinked_telegram_user_is_200_success_false_not_failure(monkeypatch):
    """LABN-FE-002 semantics: 200 + success:false — the patient did NOT
    receive the report; the frontend must show an honest failure."""
    patient = SimpleNamespace(phone="+998901234567")
    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _pid: patient,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: None,
        raising=False,
    )
    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    result = await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)

    assert result["success"] is False
    assert result["message"]


@pytest.mark.asyncio
async def test_notification_preference_disabled_is_200_success_false(monkeypatch):
    patient = SimpleNamespace(phone="+998901234567")
    telegram_user = SimpleNamespace(
        chat_id=998877,
        language_code="ru",
        notifications_enabled=True,
        lab_notifications=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _pid: patient,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: telegram_user,
        raising=False,
    )
    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    result = await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)

    assert result["success"] is False
    assert result["message"]


@pytest.mark.asyncio
async def test_instance_of_another_patient_is_409(monkeypatch):
    _patch_success_flow(monkeypatch, instance=_synthetic_instance(patient_id=999))

    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    with pytest.raises(Exception) as excinfo:
        await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)
    assert getattr(excinfo.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_draft_instance_is_409_only_finalized_can_be_sent(monkeypatch):
    _patch_success_flow(monkeypatch, instance=_synthetic_instance(status="IN_PROGRESS"))

    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    with pytest.raises(Exception) as excinfo:
        await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)
    assert getattr(excinfo.value, "status_code", None) == 409
    assert "finalized" in str(getattr(excinfo.value, "detail", "")).lower()


@pytest.mark.asyncio
async def test_doctor_outside_allowed_scope_is_403(monkeypatch):
    """The doctor-scope guard from the legacy send must stay in force for the
    instance route (Doctor only sees own patients)."""
    _patch_success_flow(monkeypatch)

    doctor = SimpleNamespace(
        id=7, role="Doctor", is_superuser=False, is_active=True, username="synthetic-doc"
    )

    def _deny(_db, _patient_id, _current_user):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Access denied")

    monkeypatch.setattr(
        telegram_notifications,
        "_ensure_doctor_can_send_patient_lab_results",
        _deny,
        raising=False,
    )

    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    with pytest.raises(Exception) as excinfo:
        await handler(payload=payload, db=object(), current_user=doctor)
    assert getattr(excinfo.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_bot_send_failure_is_500_not_false_success(monkeypatch):
    bot_service, _, _ = _patch_success_flow(monkeypatch)
    bot_service._send_document = AsyncMock(return_value=(False, None, "telegram_api_error"))

    handler = telegram_notifications.send_lab_report_instance_notification
    payload = telegram_notifications.LabReportInstanceNotificationRequest(
        patient_id=444, report_instance_id=91
    )

    with pytest.raises(Exception) as excinfo:
        await handler(payload=payload, db=object(), current_user=SYNTHETIC_ADMIN)
    assert getattr(excinfo.value, "status_code", None) == 500
