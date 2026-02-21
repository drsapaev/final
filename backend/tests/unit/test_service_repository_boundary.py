from __future__ import annotations

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
