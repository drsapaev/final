from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.domain.context_registry import DomainContext, detect_context

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
_SCANNED_DIRS = ("services", "repositories")

# Temporary migration allowlist for legacy direct service-to-service calls.
# These edges must be moved to context facades/contracts in subsequent tasks.
_TEMP_ALLOWED_CROSS_CONTEXT_IMPORTS: set[tuple[str, str]] = {
    ("app.services.appointment_flow_api_service", "app.services.emr_phrase_indexer"),
    ("app.services.billing_service", "app.services.queue_service"),
    ("app.services.morning_assignment", "app.services.queue_service"),
    ("app.services.payment_init_service", "app.services.queue_service"),
    ("app.services.payment_webhook", "app.services.visit_payment_integration"),
    ("app.services.visit_confirmation_service", "app.services.queue_service"),
}


@dataclass(frozen=True)
class BoundaryViolation:
    caller_module: str
    target_module: str
    caller_context: DomainContext
    target_context: DomainContext
    line_number: int
    reason: str


def _module_name_from_path(file_path: Path) -> str:
    relative = file_path.relative_to(APP_ROOT).with_suffix("")
    return "app." + ".".join(relative.parts)


def _resolve_relative_module(
    *,
    caller_module: str,
    module: str | None,
    level: int,
) -> str | None:
    caller_pkg_parts = caller_module.split(".")[:-1]
    prefix_size = len(caller_pkg_parts) - (level - 1)
    if prefix_size <= 0:
        return None

    prefix_parts = caller_pkg_parts[:prefix_size]
    if module:
        return ".".join([*prefix_parts, module])
    return ".".join(prefix_parts)


def _extract_imported_modules(file_path: Path, caller_module: str) -> list[tuple[str, int]]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level > 0:
            resolved = _resolve_relative_module(
                caller_module=caller_module,
                module=node.module,
                level=node.level,
            )
        else:
            resolved = node.module

        if resolved:
            imports.append((resolved, node.lineno))
            # Handle `from app.services import queue_service` by also checking
            # the fully qualified module path (`app.services.queue_service`).
            if resolved in {"app.services", "app.repositories", "app.domain.contracts"}:
                for alias in node.names:
                    if alias.name != "*":
                        imports.append((f"{resolved}.{alias.name}", node.lineno))
        elif node.level > 0:
            package_only = _resolve_relative_module(
                caller_module=caller_module,
                module=None,
                level=node.level,
            )
            if package_only:
                for alias in node.names:
                    if alias.name != "*":
                        imports.append((f"{package_only}.{alias.name}", node.lineno))

    return imports


def _iter_candidate_modules() -> list[tuple[str, Path]]:
    modules: list[tuple[str, Path]] = []
    for folder in _SCANNED_DIRS:
        for file_path in (APP_ROOT / folder).rglob("*.py"):
            if file_path.name == "__init__.py":
                continue
            module_name = _module_name_from_path(file_path)
            modules.append((module_name, file_path))
    return modules


def _is_direct_context_dependency_violation(
    caller_module: str,
    target_module: str,
    caller_context: DomainContext,
    target_context: DomainContext,
) -> tuple[bool, str]:
    if caller_context == target_context:
        return False, ""

    if target_module.startswith("app.services.context_facades"):
        return False, ""
    if target_module.startswith("app.domain.contracts"):
        return False, ""

    if (caller_module, target_module) in _TEMP_ALLOWED_CROSS_CONTEXT_IMPORTS:
        return False, ""

    if target_module.startswith("app.repositories."):
        return (
            True,
            "cross-context repository import (must use target facade/contract)",
        )

    if target_module.startswith("app.services."):
        return (
            True,
            "cross-context service import (must use target facade/contract)",
        )

    return False, ""


def test_context_boundaries_block_direct_cross_context_dependencies() -> None:
    violations: list[BoundaryViolation] = []

    for caller_module, file_path in _iter_candidate_modules():
        caller_context = detect_context(caller_module)
        if caller_context is None:
            continue

        for target_module, line_number in _extract_imported_modules(file_path, caller_module):
            if not (
                target_module.startswith("app.services.")
                or target_module.startswith("app.repositories.")
                or target_module.startswith("app.domain.contracts.")
            ):
                continue

            target_context = detect_context(target_module)
            if target_context is None:
                continue

            is_violation, reason = _is_direct_context_dependency_violation(
                caller_module=caller_module,
                target_module=target_module,
                caller_context=caller_context,
                target_context=target_context,
            )
            if not is_violation:
                continue

            violations.append(
                BoundaryViolation(
                    caller_module=caller_module,
                    target_module=target_module,
                    caller_context=caller_context,
                    target_context=target_context,
                    line_number=line_number,
                    reason=reason,
                )
            )

    if violations:
        formatted = [
            "Context boundary violations (module -> forbidden import):",
            *[
                (
                    f"- {v.caller_module}:{v.line_number} -> {v.target_module} "
                    f"[{v.caller_context.value} -> {v.target_context.value}] ({v.reason})"
                )
                for v in sorted(
                    violations,
                    key=lambda item: (item.caller_module, item.target_module, item.line_number),
                )
            ],
        ]
        pytest.fail("\n".join(formatted))
