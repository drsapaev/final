from __future__ import annotations

import ast
from pathlib import Path
import unittest


SOURCE_PATH = Path(__file__).resolve().parents[2] / "app" / "services" / "notifications.py"
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
SOURCE_TREE = ast.parse(SOURCE_TEXT)


def _send_push_node() -> ast.AsyncFunctionDef:
    for node in ast.walk(SOURCE_TREE):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "send_push":
            return node
    raise AssertionError("send_push async function not found")


def _logger_calls() -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(_send_push_node()):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "logger":
            continue
        if node.func.attr not in {"warning", "error"}:
            continue
        calls.append(node)
    return calls


def _string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _find_logger_call(message: str) -> ast.Call:
    for call in _logger_calls():
        if call.args and _string_arg(call.args[0]) == message:
            return call
    raise AssertionError(f"logger call not found for message: {message}")


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


def _send_push_source() -> str:
    source = ast.get_source_segment(SOURCE_TEXT, _send_push_node())
    if source is None:
        raise AssertionError("send_push source segment not found")
    return source


class NotificationsPushLoggingTest(unittest.TestCase):
    def test_missing_user_log_redacts_user_id(self) -> None:
        call = _find_logger_call("Push target user not found")
        self.assertEqual(_extra_keys(call), {"notification_type"})

    def test_notification_history_log_redacts_identifiers_and_raw_error(self) -> None:
        call = _find_logger_call("Failed to save notification history")
        self.assertEqual(_extra_keys(call), {"notification_type", "error_type"})

    def test_websocket_log_redacts_identifiers_and_raw_error(self) -> None:
        call = _find_logger_call("Failed to send WebSocket notification without DB")
        self.assertEqual(_extra_keys(call), {"notification_type", "error_type"})

    def test_top_level_push_error_log_uses_error_type_only(self) -> None:
        call = _find_logger_call("Push notification delivery failed")
        self.assertEqual(_extra_keys(call), {"notification_type", "error_type"})

    def test_send_push_source_no_longer_logs_user_id_or_raw_error_strings(self) -> None:
        send_push_source = _send_push_source()
        self.assertNotIn('extra={"user_id": user_id', send_push_source)
        self.assertNotIn('"error": str(', send_push_source)
        self.assertNotIn('Ошибка отправки Push: {e}', send_push_source)


if __name__ == "__main__":
    unittest.main()
