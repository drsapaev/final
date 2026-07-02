from __future__ import annotations

import ast
from pathlib import Path
import unittest


SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "morning_assignment.py"
)
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
SOURCE_TREE = ast.parse(SOURCE_TEXT)


def _logger_info_calls() -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(SOURCE_TREE):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "info":
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "logger":
            continue
        calls.append(node)
    return calls


def _string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _contains_patient_id(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Attribute) and child.attr == "patient_id"
        for child in ast.walk(node)
    )


def _find_info_call(message: str) -> ast.Call:
    for call in _logger_info_calls():
        if call.args and _string_arg(call.args[0]) == message:
            return call
    raise AssertionError(f"logger.info call not found for message: {message}")


class MorningAssignmentLoggingTest(unittest.TestCase):
    def test_assignment_log_redacts_patient_id(self) -> None:
        message = "Assigned number %s in queue %s through SSOT, services: %s"
        call = _find_info_call(message)

        self.assertEqual(len(call.args), 4)
        self.assertFalse(any(_contains_patient_id(arg) for arg in call.args[1:]))
        self.assertNotIn("for patient %s", SOURCE_TEXT)

    def test_existing_entry_log_redacts_patient_id(self) -> None:
        message = "Active queue entry already exists for queue %s"
        call = _find_info_call(message)

        self.assertEqual(len(call.args), 2)
        self.assertFalse(any(_contains_patient_id(arg) for arg in call.args[1:]))
        self.assertNotIn("already has active queue entry", SOURCE_TEXT)

    def test_claim_error_messages_redact_patient_id(self) -> None:
        self.assertNotIn("and patient_id={patient_id}", SOURCE_TEXT)


if __name__ == "__main__":
    unittest.main()
