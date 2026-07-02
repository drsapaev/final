from __future__ import annotations

import asyncio
from pathlib import Path

from app.crud import print_config as crud_print
from app.api.v1.endpoints import print_api as print_api_module
from app.models.print_config import PrinterConfig, PrintTemplate
from app.services.print_service import PrintService


def _create_printer(
    db_session,
    *,
    name: str,
    display_name: str,
    printer_type: str,
    is_default: bool = False,
) -> PrinterConfig:
    printer = PrinterConfig(
        name=name,
        display_name=display_name,
        printer_type=printer_type,
        connection_type="mock",
        encoding="utf-8",
        active=True,
        is_default=is_default,
    )
    db_session.add(printer)
    db_session.commit()
    db_session.refresh(printer)
    return printer


def _create_template(
    db_session,
    *,
    printer_id: int,
    name: str,
    display_name: str,
    template_type: str,
    template_content: str,
) -> PrintTemplate:
    template = PrintTemplate(
        printer_id=printer_id,
        name=name,
        display_name=display_name,
        template_type=template_type,
        template_content=template_content,
        language="ru",
        font_size=12,
        line_spacing=1,
        active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def test_print_service_selects_document_type_printers_and_uses_mock_paths(db_session):
    ticket_printer = _create_printer(
        db_session,
        name="ticket_printer",
        display_name="Термопринтер кассы",
        printer_type="ESC/POS",
        is_default=True,
    )
    lab_printer = _create_printer(
        db_session,
        name="lab_printer",
        display_name="A4 принтер лаборатории",
        printer_type="A4",
    )
    prescription_printer = _create_printer(
        db_session,
        name="prescription_printer",
        display_name="A5 принтер рецептов",
        printer_type="A5",
    )

    _create_template(
        db_session,
        printer_id=ticket_printer.id,
        name="ticket_template",
        display_name="Шаблон талона",
        template_type="ticket",
        template_content="{{ queue_number }}|{{ doctor_name }}",
    )
    _create_template(
        db_session,
        printer_id=ticket_printer.id,
        name="receipt_template",
        display_name="Шаблон чека",
        template_type="receipt",
        template_content="{{ payment.number }}|{{ patient.full_name }}",
    )
    _create_template(
        db_session,
        printer_id=lab_printer.id,
        name="lab_results_template",
        display_name="Шаблон результатов",
        template_type="lab_results",
        template_content="<html><body>{{ lab_order.number }}|{{ patient.full_name }}</body></html>",
    )
    _create_template(
        db_session,
        printer_id=prescription_printer.id,
        name="prescription_template",
        display_name="Шаблон рецепта",
        template_type="prescription",
        template_content="<html><body>{{ prescription.number }}|{{ patient.full_name }}</body></html>",
    )

    service = PrintService(db_session)

    assert crud_print.get_default_printer_for_type(db_session, "receipt").name == "ticket_printer"
    assert crud_print.get_default_printer_for_type(db_session, "ticket").name == "ticket_printer"
    assert crud_print.get_default_printer_for_type(db_session, "lab_results").name == "lab_printer"
    assert crud_print.get_default_printer_for_type(db_session, "prescription").name == "prescription_printer"

    ticket_result = asyncio.run(
        service.print_document(
            document_type="ticket",
            document_data={
                "queue_number": "A-12",
                "doctor_name": "Dr. Smoke",
            },
        )
    )
    assert ticket_result["success"] is True
    assert ticket_result["printer"] == "Термопринтер кассы"
    assert ticket_result["result"]["method"] == "mock"

    lab_result = asyncio.run(
        service.print_document(
            document_type="lab_results",
            document_data={
                "lab_order": {"number": "LAB-1"},
                "patient": {"full_name": "Test Patient"},
            },
        )
    )
    assert lab_result["success"] is True
    assert lab_result["printer"] == "A4 принтер лаборатории"
    assert lab_result["result"]["method"] == "mock"

    prescription_result = asyncio.run(
        service.print_document(
            document_type="prescription",
            document_data={
                "prescription": {"number": "RX-1"},
                "patient": {"full_name": "Test Patient"},
            },
        )
    )
    assert prescription_result["success"] is True
    assert prescription_result["printer"] == "A5 принтер рецептов"
    assert prescription_result["result"]["method"] == "mock"


def test_print_printers_endpoint_returns_database_printers(
    client, auth_headers, db_session, monkeypatch
):
    _create_printer(
        db_session,
        name="ticket_printer",
        display_name="Термопринтер кассы",
        printer_type="ESC/POS",
        is_default=True,
    )
    _create_printer(
        db_session,
        name="lab_printer",
        display_name="A4 принтер лаборатории",
        printer_type="A4",
    )

    async def fake_discover_system_printers(self):
        return []

    monkeypatch.setattr(
        PrintService, "discover_system_printers", fake_discover_system_printers
    )

    client.app.dependency_overrides[print_api_module.get_print_service] = (
        lambda: PrintService(db_session)
    )
    try:
        response = client.get("/api/v1/print/printers", headers=auth_headers)
        assert response.status_code == 200

        payload = response.json()
        assert payload["total"] == 2
        printer_names = {item["name"] for item in payload["printers"]}
        assert printer_names == {"ticket_printer", "lab_printer"}
        assert any(item["status"] == "online" for item in payload["printers"])
    finally:
        client.app.dependency_overrides.pop(print_api_module.get_print_service, None)


def test_print_service_prefers_discovered_system_printers_over_mock(
    db_session, monkeypatch
):
    _create_printer(
        db_session,
        name="ticket_printer",
        display_name="Термопринтер кассы",
        printer_type="ESC/POS",
        is_default=True,
    )

    service = PrintService(db_session)

    async def fake_discover_system_printers(self):
        return [
            {
                "name": "Canon MF3010",
                "display_name": "Canon MF3010",
                "printer_type": "A4",
                "connection_type": "local",
                "device_path": "Canon MF3010",
                "paper_width": 210,
                "paper_height": 297,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": True,
                "status": "online",
                "driver_name": "Canon MF3010",
                "location": "",
            }
        ]

    monkeypatch.setattr(
        PrintService, "discover_system_printers", fake_discover_system_printers
    )

    synced = asyncio.run(service.sync_system_printers())
    assert synced
    assert synced[0].name == "Canon MF3010"
    assert synced[0].connection_type == "local"

    default_printer = crud_print.get_default_printer_for_type(db_session, "lab_results")
    assert default_printer is not None
    assert default_printer.name == "Canon MF3010"
    assert default_printer.connection_type == "local"


def test_print_printers_endpoint_uses_discovered_system_printers(
    client, auth_headers, db_session, monkeypatch
):
    _create_printer(
        db_session,
        name="ticket_printer",
        display_name="Термопринтер кассы",
        printer_type="ESC/POS",
        is_default=True,
    )

    service = PrintService(db_session)

    async def fake_discover_system_printers(self):
        return [
            {
                "name": "Canon MF3010",
                "display_name": "Canon MF3010",
                "printer_type": "A4",
                "connection_type": "local",
                "device_path": "Canon MF3010",
                "paper_width": 210,
                "paper_height": 297,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": True,
                "status": "online",
                "driver_name": "Canon MF3010",
                "location": "",
            },
            {
                "name": "Thermal XPrinter",
                "display_name": "Thermal XPrinter",
                "printer_type": "ESC/POS",
                "connection_type": "local",
                "device_path": "Thermal XPrinter",
                "paper_width": 58,
                "paper_height": None,
                "margins": None,
                "encoding": "utf-8",
                "active": True,
                "is_default": False,
                "status": "online",
                "driver_name": "XPrinter",
                "location": "",
            },
        ]

    monkeypatch.setattr(
        PrintService, "discover_system_printers", fake_discover_system_printers
    )

    client.app.dependency_overrides[print_api_module.get_print_service] = (
        lambda: service
    )
    try:
        response = client.get("/api/v1/print/printers", headers=auth_headers)
        assert response.status_code == 200

        payload = response.json()
        assert payload["total"] == 2

        printer_names = {item["name"] for item in payload["printers"]}
        assert printer_names == {"Canon MF3010", "Thermal XPrinter"}
        assert all(item["connection_type"] == "local" for item in payload["printers"])
    finally:
        client.app.dependency_overrides.pop(print_api_module.get_print_service, None)


def test_lab_results_prints_with_missing_referring_doctor_using_real_template(db_session):
    lab_printer = _create_printer(
        db_session,
        name="lab_printer",
        display_name="A4 принтер лаборатории",
        printer_type="A4",
        is_default=True,
    )

    template_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "templates"
        / "print"
        / "lab_results_a4.j2"
    )
    _create_template(
        db_session,
        printer_id=lab_printer.id,
        name="lab_results_template",
        display_name="Шаблон результатов",
        template_type="lab_results",
        template_content=template_path.read_text(encoding="utf-8"),
    )

    service = PrintService(db_session)

    result = asyncio.run(
        service.print_document(
            document_type="lab_results",
            document_data={
                "lab_order": {
                    "number": "LAB-REAL-1",
                    "collection_date": "2026-04-02T10:00:00+05:00",
                    "ready_date": "2026-04-02T12:00:00+05:00",
                    "laboratory_name": "Lab",
                    "study_type": "CBC",
                    "urgency_name": "Routine",
                },
                "lab_results": [
                    {
                        "parameter_name": "WBC",
                        "value": "5.4",
                        "unit": "10^9/L",
                        "reference_range": "4.0-10.0",
                    }
                ],
                "patient": {
                    "full_name": "Test Patient",
                    "birth_date": "1990-01-01",
                    "age": 36,
                    "gender_name": "Male",
                },
            },
        )
    )

    assert result["success"] is True
    assert result["result"]["method"] == "mock"
