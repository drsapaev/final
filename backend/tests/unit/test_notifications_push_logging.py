from __future__ import annotations

import ast
from pathlib import Path
import unittest


SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "notifications.py"
)
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
SOURCE_TREE = ast.parse(SOURCE_TEXT)


def _async_function_node(name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(SOURCE_TREE):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} async function not found")


def _logger_calls_in(node: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if not isinstance(child.func.value, ast.Name):
            continue
        if child.func.value.id != "logger":
            continue
        if child.func.attr not in {"warning", "error"}:
            continue
        calls.append(child)
    return calls


def _string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_logger_call_in(node: ast.AST, message: str) -> ast.Call:
    for call in _logger_calls_in(node):
        if call.args and _string_arg(call.args[0]) == message:
            return call
    raise AssertionError(f"logger call not found for message: {message}")


def _find_module_logger_call(message: str) -> ast.Call:
    return _find_logger_call_in(SOURCE_TREE, message)


def _send_push_node() -> ast.AsyncFunctionDef:
    return _async_function_node("send_push")


def _send_push_logger_call(message: str) -> ast.Call:
    return _find_logger_call_in(_send_push_node(), message)


def _extra_keys(call: ast.Call) -> set[str]:
    for keyword in call.keywords:
        if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
            continue
        keys: set[str] = set()
        for key in keyword.value.keys:
            string_key = _string_arg(key)
            if string_key is not None:
                keys.add(string_key)
        return keys
    return set()


def _function_source(name: str) -> str:
    source = ast.get_source_segment(SOURCE_TEXT, _async_function_node(name))
    if source is None:
        raise AssertionError(f"{name} source segment not found")
    return source


class NotificationsPushLoggingTest(unittest.TestCase):
    def test_missing_user_log_redacts_user_id(self) -> None:
        call = _send_push_logger_call("Push target user not found")
        self.assertEqual(_extra_keys(call), set())

    def test_notification_history_log_redacts_identifiers_and_raw_error(self) -> None:
        call = _send_push_logger_call("Failed to save notification history")
        self.assertEqual(_extra_keys(call), {"error_type"})

    def test_websocket_log_redacts_identifiers_and_raw_error(self) -> None:
        call = _send_push_logger_call("Failed to send WebSocket notification without DB")
        self.assertEqual(_extra_keys(call), {"error_type"})

    def test_top_level_push_error_log_uses_error_type_only(self) -> None:
        call = _send_push_logger_call("Push notification delivery failed")
        self.assertEqual(_extra_keys(call), {"error_type"})

    def test_send_push_source_no_longer_logs_user_id_or_raw_error_strings(self) -> None:
        send_push_source = _function_source("send_push")
        self.assertNotIn('extra={"user_id": user_id', send_push_source)
        self.assertNotIn('"error": str(', send_push_source)
        self.assertNotIn("Ошибка отправки Push:", send_push_source)

    def test_appointment_time_parse_warning_redacts_identifiers(self) -> None:
        call = _find_module_logger_call("Failed to parse appointment time for notification")
        self.assertEqual(_extra_keys(call), {"has_appointment_time"})

    def test_appointment_notification_missing_entities_redact_identifiers(self) -> None:
        appointment_call = _find_module_logger_call(
            "Appointment notification skipped: appointment not found"
        )
        patient_call = _find_module_logger_call(
            "Appointment notification skipped: patient not found"
        )
        self.assertEqual(_extra_keys(appointment_call), {"notification_type"})
        self.assertEqual(_extra_keys(patient_call), {"notification_type"})

    def test_payment_notification_missing_patient_redacts_identifiers(self) -> None:
        call = _find_module_logger_call("Payment notification skipped: patient not found")
        self.assertEqual(_extra_keys(call), {"notification_type"})

    def test_fixed_notification_functions_no_longer_log_sensitive_ids(self) -> None:
        appointment_confirmation_source = _function_source(
            "send_appointment_confirmation"
        )
        appointment_notification_source = _function_source(
            "send_appointment_notification"
        )
        payment_notification_source = _function_source(
            "send_payment_notification_by_id"
        )

        self.assertNotIn(
            '"appointment_time": appointment.appointment_time',
            appointment_confirmation_source,
        )
        self.assertNotIn(
            "Запись не найдена:", appointment_notification_source
        )
        self.assertNotIn(
            "Пациент не найден:", appointment_notification_source
        )
        self.assertNotIn(
            "Пациент не найден:", payment_notification_source
        )


if __name__ == "__main__":
    unittest.main()
