from __future__ import annotations

import ast
import re
from pathlib import Path


def _function_block(path: Path, function_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
        if isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == function_name:
                    end = getattr(inner, "end_lineno", inner.lineno)
                    return "\n".join(lines[inner.lineno - 1 : end])
    raise AssertionError(f"Function {function_name} not found in {path}")


def test_queue_domain_service_avoids_direct_session_calls() -> None:
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "queue_domain_service.py"
    )
    text = service_path.read_text(encoding="utf-8")
    direct_db_call = re.search(
        r"\bdb\.(query|add|commit|rollback|refresh|execute|delete|flush)\(",
        text,
    )
    assert direct_db_call is None


def test_queue_reorder_status_reads_use_domain_service() -> None:
    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "queue_reorder_api_service.py"
    )
    for function_name in ("get_queue_status", "get_queue_status_by_specialist"):
        block = _function_block(service_path, function_name)
        assert "self.domain_service" in block
        assert "list_active_entries" not in block


def test_queue_cabinet_read_handlers_use_domain_service() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "queue_cabinet_management.py"
    )
    for function_name in ("get_queues_cabinet_info", "get_queue_cabinet_info"):
        block = _function_block(endpoint_path, function_name)
        assert "QueueDomainService(db)" in block
        assert "QueueCabinetManagementApiService(db)" not in block
