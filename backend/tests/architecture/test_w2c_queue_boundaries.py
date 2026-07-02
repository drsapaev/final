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
            return "\
".join(lines[node.lineno - 1 : end])
        if isinstance(node, ast.ClassDef):
            for inner in node.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == function_name:
                    end = getattr(inner, "end_lineno", inner.lineno)
                    return "\
".join(lines[inner.lineno - 1 : end])
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


def test_queue_limits_status_handler_uses_domain_service() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "queue_limits.py"
    )
    block = _function_block(endpoint_path, "get_queue_status_with_limits")
    assert "QueueDomainService(db)" in block
    assert "QueueLimitsApiService(db).get_queue_status_with_limits" not in block

def test_service_queue_metadata_handlers_use_queue_domain_service() -> None:
    endpoint_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "services.py"
    )
    for function_name in ("get_queue_groups", "get_service_code_mappings"):
        block = _function_block(endpoint_path, function_name)
        assert "QueueDomainService(db)" in block
        assert "ServicesApiService(db)" not in block
        assert "db.query(" not in block


def test_queue_route_surface_is_explicitly_classified() -> None:
    api_path = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "api.py"
    text = api_path.read_text(encoding="utf-8")

    assert (
        'api_router.include_router(qr_queue.router, prefix="/queue", tags=["qr-queue"])'
        in text
    )
    assert (
        'api_router.include_router(queues.router, prefix="/queues", tags=["queues"])'
        in text
    )
    assert (
        'api_router.include_router(online_queue_new.router, tags=["online-queue-new"])'
        in text
    )
    assert (
        'api_router.include_router(queue_router, prefix="/queue/legacy", tags=["queue-legacy"])'
        in text
    )
    assert re.search(
        r"queue_reorder\.router,\s*prefix=\"/queue/reorder\"",
        text,
        flags=re.DOTALL,
    )
    assert re.search(
        r"queue_position\.router,\s*prefix=\"/queue/position\"",
        text,
        flags=re.DOTALL,
    )


def test_queue_groups_resolve_explicit_tags_and_tabs() -> None:
    from app.services.service_mapping import QUEUE_GROUPS, resolve_queue_group_key

    service_mapping_path = (
        Path(__file__).resolve().parents[2] / "app" / "services" / "service_mapping.py"
    )
    assert service_mapping_path.exists()

    expected_groups = {
        "cardiology",
        "ecg",
        "dermatology",
        "dental",
        "laboratory",
        "procedures",
    }
    assert expected_groups.issubset(set(QUEUE_GROUPS))

    tab_keys: list[str] = []
    queue_tags: list[str] = []
    for group_key, group_data in QUEUE_GROUPS.items():
        tab_key = group_data["tab_key"]
        queue_tag = group_data["queue_tag"]
        tab_keys.append(tab_key)
        queue_tags.append(queue_tag)

        assert resolve_queue_group_key(department_key=group_key) == group_key
        assert resolve_queue_group_key(department_key=tab_key) == group_key
        assert resolve_queue_group_key(queue_tag=queue_tag) == group_key

    assert len(tab_keys) == len(set(tab_keys))
    assert len(queue_tags) == len(set(queue_tags))
