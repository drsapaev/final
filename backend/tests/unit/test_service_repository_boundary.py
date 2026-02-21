from __future__ import annotations

import re
from pathlib import Path


ROUTER_MARKER = "# --- API Router moved from app/api/v1/endpoints/"


def _service_logic_block(module_name: str) -> str:
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / f"{module_name}_api_service.py"
    )
    text = service_path.read_text(encoding="utf-8")
    return text.split(ROUTER_MARKER, maxsplit=1)[0]


def test_appointments_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("appointments")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_visits_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("visits")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_messages_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("messages")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_cashier_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("cashier")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_services_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("services")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_dental_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("dental")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_queue_cabinet_management_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("queue_cabinet_management")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_payments_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("payments")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_dynamic_pricing_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("dynamic_pricing")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_qr_queue_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("qr_queue")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_admin_departments_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("admin_departments")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_registrar_integration_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("registrar_integration")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_doctor_integration_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("doctor_integration")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_registrar_wizard_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("registrar_wizard")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_force_majeure_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("force_majeure")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_salary_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("salary")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_patient_appointments_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("patient_appointments")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_roles_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("roles")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_global_search_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("global_search")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_specialized_panels_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("specialized_panels")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_queue_reorder_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("queue_reorder")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_billing_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("billing")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_queue_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("queue")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_registrar_notifications_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("registrar_notifications")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None
