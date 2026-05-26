from __future__ import annotations

import ast
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "api"
    / "v1"
    / "endpoints"
    / "appointment_flow.py"
)

WRITE_HANDLERS = {
    "create_or_update_emr",
    "save_emr",
    "create_or_update_prescription",
    "save_prescription",
    "complete_visit",
}

READ_HANDLERS = {
    "get_emr",
    "get_prescription",
    "get_appointment_status",
    "resolve_canonical_visit",
}


def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _resolve_calls(fn: ast.FunctionDef) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_resolve_appointment_and_visit"
        ):
            calls.append(node)
    return calls


def _allow_visit_fallback_kw(call: ast.Call) -> bool | None:
    for keyword in call.keywords:
        if keyword.arg == "allow_visit_fallback":
            return keyword.value.value if isinstance(keyword.value, ast.Constant) else None
    return None


def test_clinical_write_handlers_disable_legacy_visit_id_fallback() -> None:
    functions = _functions()

    for handler_name in WRITE_HANDLERS:
        calls = _resolve_calls(functions[handler_name])
        assert calls, f"{handler_name} must resolve appointment/visit before writing"
        assert any(_allow_visit_fallback_kw(call) is False for call in calls), (
            f"{handler_name} must not silently treat a missing appointment_id as visit_id"
        )


def test_read_handlers_keep_legacy_visit_id_fallback() -> None:
    functions = _functions()

    for handler_name in READ_HANDLERS:
        calls = _resolve_calls(functions[handler_name])
        assert calls, f"{handler_name} must resolve appointment/visit before reading"
        assert all(_allow_visit_fallback_kw(call) is not False for call in calls), (
            f"{handler_name} should remain read-compatible with legacy visit_id fallback"
        )
