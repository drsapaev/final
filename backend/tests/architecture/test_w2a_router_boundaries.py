from __future__ import annotations

import re
import ast
from pathlib import Path


def test_messages_router_uses_service_router_import() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "messages.py"
    )
    text = endpoint_path.read_text(encoding="utf-8")
    assert "from app.services.messages_api_service import router" in text


def test_messages_router_has_no_direct_db_calls() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "messages.py"
    )
    text = endpoint_path.read_text(encoding="utf-8")
    forbidden = re.search(
        r"\bdb\.(query|add|commit|refresh|rollback|delete|execute|flush)\(",
        text,
    )
    assert forbidden is None


def _function_block(path: Path, function_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
    raise AssertionError(f"Function {function_name} not found in {path}")


def test_services_catalog_handlers_use_service_layer() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "services.py"
    )
    safe_handlers = [
        "list_service_categories",
        "create_service_category",
        "update_service_category",
        "delete_service_category",
        "list_services",
        "get_service",
        "create_service",
        "update_service",
        "delete_service",
        "list_doctors_temp",
    ]
    for handler_name in safe_handlers:
        block = _function_block(endpoint_path, handler_name)
        assert "ServicesApiService(db)" in block
        forbidden = re.search(
            r"\bdb\.(query|add|commit|refresh|rollback|delete|execute|flush)\(",
            block,
        )
        assert forbidden is None, handler_name


def test_visits_read_only_handlers_use_service_layer() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "visits.py"
    )
    safe_handlers = [
        "list_visits",
        "get_visit",
    ]
    for handler_name in safe_handlers:
        block = _function_block(endpoint_path, handler_name)
        assert "VisitsApiService(db)" in block
        forbidden = re.search(
            r"\bdb\.(query|add|commit|refresh|rollback|delete|execute|flush)\(",
            block,
        )
        assert forbidden is None, handler_name
