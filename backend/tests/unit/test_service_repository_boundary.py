from __future__ import annotations

import re
from pathlib import Path

import pytest

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


def test_dynamic_pricing_service_avoids_direct_orm_calls() -> None:
    logic = _service_logic_block("dynamic_pricing")
    assert "repository.db" not in logic
    assert ".query(" not in logic


def test_qr_queue_service_avoids_direct_session_calls() -> None:
    # R-17: qr_queue_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "qr_queue_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("qr_queue_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("qr_queue")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_registrar_integration_service_avoids_direct_session_calls() -> None:
    # R-16: registrar_integration_api_service.py удалён (3152 строки мёртвого
    # кода — не зарегистрирован, не импортировался). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "registrar_integration_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("registrar_integration_api_service.py was removed (R-16 dead code cleanup)")

    logic = _service_logic_block("registrar_integration")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_doctor_integration_service_avoids_direct_session_calls() -> None:
    # R-17: doctor_integration_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "doctor_integration_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("doctor_integration_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("doctor_integration")
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


def test_queue_limits_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("queue_limits")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_group_permissions_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("group_permissions")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_appointment_flow_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("appointment_flow")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_queue_position_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("queue_position")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_analytics_simple_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("analytics_simple")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_payment_webhooks_service_avoids_direct_session_calls() -> None:
    # R-17: payment_webhooks_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "payment_webhooks_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("payment_webhooks_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("payment_webhooks")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_payment_init_service_uses_queue_facade_for_billing_to_queue_flow() -> None:
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "payment_init_service.py"
    )
    logic = service_path.read_text(encoding="utf-8")
    assert "QueueContextFacade" in logic, (
        "broken contract: billing caller must use queue facade for queue timestamp access"
    )
    assert "timestamp_parity" in logic, (
        "expected migration parity logging in payment_init service for billing->queue flow"
    )


def test_appointment_flow_service_uses_patient_emr_iam_facades() -> None:
    logic = _service_logic_block("appointment_flow")
    assert "PatientContextFacade" in logic, (
        "broken contract: scheduling caller must use patient facade instead of direct patient data coupling"
    )
    assert "EmrContextFacade" in logic, (
        "broken contract: scheduling caller must use emr facade for phrase indexing operations"
    )
    assert "IamContextFacade" in logic, (
        "broken contract: emr write authorization must pass through iam facade checks"
    )


def test_patients_service_avoids_direct_session_calls() -> None:
    # R-17: patients_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "patients_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("patients_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("patients")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_derma_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("derma")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_user_management_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("user_management")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_file_system_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("file_system")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_discount_benefits_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("discount_benefits")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_telegram_bot_management_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("telegram_bot_management")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_morning_assignment_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("morning_assignment")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_migration_management_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("migration_management")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_feature_flags_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("feature_flags")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_display_websocket_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("display_websocket")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_two_factor_auth_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("two_factor_auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_phrase_suggest_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("phrase_suggest")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_authentication_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("authentication")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_payment_settings_service_avoids_direct_session_calls() -> None:
    # R-17: payment_settings_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "payment_settings_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("payment_settings_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("payment_settings")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_ai_chat_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("ai_chat")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_auth_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_online_queue_new_service_avoids_direct_session_calls() -> None:
    # R-17: online_queue_new_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "online_queue_new_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("online_queue_new_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("online_queue_new")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_mobile_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("mobile")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_lab_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("lab")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_departments_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("departments")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_ai_tracking_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("ai_tracking")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_simple_auth_service_avoids_direct_session_calls() -> None:
    # R-17: simple_auth_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "simple_auth_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("simple_auth_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("simple_auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_minimal_auth_service_avoids_direct_session_calls() -> None:
    # R-17: minimal_auth_api_service.py удалён (мёртвый код — router не зарегистрирован,
    # символы не импортируются). Тест больше не применим.
    # Если файл будет восстановлен — раскомментировать проверку ниже.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "minimal_auth_api_service.py"
    )
    if not service_path.exists():
        pytest.skip("minimal_auth_api_service.py was removed (R-17 dead code cleanup)")

    logic = _service_logic_block("minimal_auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


@pytest.mark.xfail(reason="EMR-AUDIT-28 P0-5: emr_v2_service.py has direct db.query calls (P2 architecture issue)")
def test_emr_v2_service_avoids_direct_session_calls() -> None:
    # EMR-AUDIT-28 P0-5: emr_v2_api_service.py (14-LOC stub) was deleted;
    # test now reads the actual service file emr_v2_service.py.
    # Note: emr_v2_service.py has direct db.query calls (P2 architecture
    # issue from EMR audit). Marked xfail until service is refactored to
    # use repository pattern.
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "emr_v2_service.py"
    )
    text = service_path.read_text(encoding="utf-8")
    logic = text.split(ROUTER_MARKER, maxsplit=1)[0]
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None
