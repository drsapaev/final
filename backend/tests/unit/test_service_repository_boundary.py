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


def test_admin_departments_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("admin_departments")
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


def test_analytics_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("analytics")
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


def test_activation_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("activation")
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


def test_admin_doctors_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("admin_doctors")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_payment_settings_service_avoids_direct_session_calls() -> None:
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
    logic = _service_logic_block("simple_auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_settings_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("settings")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_minimal_auth_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("minimal_auth")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_emr_v2_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("emr_v2")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_admin_users_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("admin_users")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None


def test_admin_ai_service_avoids_direct_session_calls() -> None:
    logic = _service_logic_block("admin_ai")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        logic,
    )
    assert direct_db_call is None
