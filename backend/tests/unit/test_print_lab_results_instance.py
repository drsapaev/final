"""
LABPRINT-FE-001 (audit 3886, round 14) — fail-first endpoint tests.

Печать лабораторного бланка: раньше POST /print/lab-results принимал
СВОБОДНЫЕ клиентские данные (lab_order/lab_results/patient) и рендерил
их без сверки с LabReportInstance. Тесты ниже падают на до-фиксном коде:
spy на PrintService.print_document получает отправленное клиентом
значение (200) вместо персистентного (100), не-FINALIZED бланк печатался,
а свободные клиентские поля принимались.
"""
from typing import Any

import pytest

from app.schemas.print_config import PrintResponse
from app.services.lab_reporting_service import LabReportingService
from app.services.print_service import PrintService


@pytest.mark.unit
class TestPrintLabResultsInstanceScoped:
    def _finalize_cbc_instance(self, db_session, test_patient, test_visit, hgb_value="100"):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(t for t in templates if t.code == "cbc_oak")
        instance = service.create_instance(
            {
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": cbc_template.id,
            }
        )
        service.bulk_upsert_values(
            instance.id,
            [{"field_key": "hgb", "value_text": hgb_value}],
        )
        service.mark_ready(instance.id)
        finalized = service.finalize(instance.id)
        db_session.flush()
        return finalized

    def _install_print_spy(self, monkeypatch, captured: dict[str, Any]):
        async def spy_print_document(self, *args, **kwargs):
            captured["document_type"] = kwargs.get("document_type")
            captured["document_data"] = kwargs.get("document_data")
            captured["printer_name"] = kwargs.get("printer_name")
            return PrintResponse(
                success=True,
                job_id=7,
                message="queued (spy)",
                printer="A4",
                error=None,
                result=None,
            )

        monkeypatch.setattr(PrintService, "print_document", spy_print_document)

    def test_prints_persisted_values_not_client_submitted(
        self, client, auth_headers, db_session, test_patient, test_visit, monkeypatch
    ):
        finalized = self._finalize_cbc_instance(db_session, test_patient, test_visit, hgb_value="100")
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)

        # До фикса: клиент отправлял свободные lab_results (значение 200,
        # пациент B) — и именно они попадали в печатный документ.
        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={
                "report_instance_id": finalized.id,
                # Свободные клиентские поля: до фикса рендерились,
                # теперь обязаны отвергаться на уровне схемы (forbid).
                "lab_results": [
                    {"field_key": "hgb", "value_text": "200", "label": "spoofed"}
                ],
                "patient": {"full_name": "Patient B (client-submitted)"},
            },
        )
        assert response.status_code == 422, response.text

    def test_document_data_reflects_persisted_instance(
        self, client, auth_headers, db_session, test_patient, test_visit, monkeypatch
    ):
        finalized = self._finalize_cbc_instance(db_session, test_patient, test_visit, hgb_value="100")
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)

        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={"report_instance_id": finalized.id},
        )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True

        data = captured["document_data"]
        # lab_order — из персистентной записи инстанса.
        assert data["lab_order"]["id"] == finalized.id
        assert data["lab_order"]["status"] == "FINALIZED"
        # Печатное значение — материализованное из БД (hgb=100), а не
        # любое клиентское.
        hgb = next(f for f in data["lab_results"] if f.get("field_key") == "hgb")
        assert hgb["value_text"] == "100"
        # Пациент — снапшот инстанса, не запрос.
        assert data["patient"]["full_name"]

    def test_rejects_non_finalized_instance(
        self, client, auth_headers, db_session, test_patient, test_visit, monkeypatch
    ):
        service = LabReportingService(db_session)
        templates = service.list_templates()
        cbc_template = next(t for t in templates if t.code == "cbc_oak")
        draft = service.create_instance(
            {
                "patient_id": test_patient.id,
                "visit_id": test_visit.id,
                "template_id": cbc_template.id,
            }
        )
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)

        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={"report_instance_id": draft.id},
        )
        # До фикса: черновик печатался без статус-проверки.
        assert response.status_code == 409, response.text
        assert "finalized" in response.json()["detail"].lower()
        assert captured.get("document_data") is None

    def test_rejects_unknown_instance(
        self, client, auth_headers, db_session, monkeypatch
    ):
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)
        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={"report_instance_id": 987654321},
        )
        assert response.status_code == 404, response.text

    def test_legacy_freeform_body_is_rejected_by_schema(
        self, client, auth_headers, db_session, monkeypatch
    ):
        """До фикса: свободный лаб-бланк (lab_order/lab_results/patient)
        принимался и рендерился как есть. Теперь extra=forbid."""
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)
        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={
                "lab_order": {"id": 1, "patient_id": 1, "visit_id": 1},
                "lab_results": [{"field_key": "hgb", "value_text": "999"}],
                "patient": {"full_name": "Anyone"},
            },
        )
        assert response.status_code == 422, response.text
        assert captured.get("document_data") is None

    def test_printer_name_passthrough(
        self, client, auth_headers, db_session, test_patient, test_visit, monkeypatch
    ):
        finalized = self._finalize_cbc_instance(db_session, test_patient, test_visit)
        captured: dict[str, Any] = {}
        self._install_print_spy(monkeypatch, captured)
        response = client.post(
            "/api/v1/print/lab-results",
            headers=auth_headers,
            json={"report_instance_id": finalized.id, "printer_name": "lab_a4"},
        )
        assert response.status_code == 200, response.text
        assert captured["printer_name"] == "lab_a4"
