from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
API_ROUTER_FILE = APP_ROOT / "api" / "v1" / "api.py"
ENDPOINTS_DIR = APP_ROOT / "api" / "v1" / "endpoints"
_FORBIDDEN_MODULE = "app.services.external_integration_service"
_ALLOWED_UNPUBLISHED_ENDPOINT_ROUTERS: set[str] = set()
_ALLOWED_DUPLICATE_API_ROUTE_METHODS: set[tuple[str, str]] = set()


@dataclass(frozen=True)
class ImportViolation:
    module: str
    file_path: str
    line_number: int
    imported: str


def _module_name_from_path(file_path: Path) -> str:
    relative = file_path.relative_to(APP_ROOT).with_suffix("")
    return "app." + ".".join(relative.parts)


def _iter_api_surface_files() -> list[Path]:
    service_api_files = (APP_ROOT / "services").glob("*_api_service.py")
    api_route_files = (APP_ROOT / "api").rglob("*.py")
    files = [*service_api_files, *api_route_files]
    return [file_path for file_path in files if file_path.name != "__init__.py"]


def _exports_router(file_path: Path) -> bool:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "router":
                    return True
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "router":
                return True
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "router" for alias in node.names):
                return True
    return False


def _endpoint_modules_exporting_router() -> set[str]:
    return {
        file_path.stem
        for file_path in ENDPOINTS_DIR.glob("*.py")
        if file_path.name != "__init__.py" and _exports_router(file_path)
    }


def _published_endpoint_modules() -> set[str]:
    tree = ast.parse(API_ROUTER_FILE.read_text(encoding="utf-8"))
    local_module_names: dict[str, str] = {}
    local_router_names: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.module == "app.api.v1.endpoints":
            for alias in node.names:
                local_module_names[alias.asname or alias.name] = alias.name
            continue

        prefix = "app.api.v1.endpoints."
        if node.module and node.module.startswith(prefix):
            endpoint_module = node.module.removeprefix(prefix).split(".", 1)[0]
            for alias in node.names:
                if alias.name == "router":
                    local_router_names[alias.asname or alias.name] = endpoint_module

    published: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router" or not node.args:
            continue

        first_arg = node.args[0]
        if isinstance(first_arg, ast.Attribute) and first_arg.attr == "router":
            value = first_arg.value
            if isinstance(value, ast.Name) and value.id in local_module_names:
                published.add(local_module_names[value.id])
            continue

        if isinstance(first_arg, ast.Name) and first_arg.id in local_router_names:
            published.add(local_router_names[first_arg.id])

    return published


def test_api_layer_does_not_import_concrete_external_providers() -> None:
    violations: list[ImportViolation] = []

    for file_path in _iter_api_surface_files():
        module_name = _module_name_from_path(file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_FORBIDDEN_MODULE):
                        violations.append(
                            ImportViolation(
                                module=module_name,
                                file_path=str(file_path.relative_to(BACKEND_ROOT)),
                                line_number=node.lineno,
                                imported=alias.name,
                            )
                        )
                continue

            if isinstance(node, ast.ImportFrom):
                imported_module = node.module or ""
                if imported_module.startswith(_FORBIDDEN_MODULE):
                    violations.append(
                        ImportViolation(
                            module=module_name,
                            file_path=str(file_path.relative_to(BACKEND_ROOT)),
                            line_number=node.lineno,
                            imported=imported_module,
                        )
                    )

    if not violations:
        return

    formatted = [
        "Interoperability boundary violations (API surface importing concrete providers):",
        *[
            (
                f"- {violation.file_path}:{violation.line_number} "
                f"({violation.module}) -> {violation.imported}"
            )
            for violation in sorted(
                violations,
                key=lambda item: (item.file_path, item.line_number, item.imported),
            )
        ],
    ]
    pytest.fail("\n".join(formatted))


def test_api_endpoint_shims_do_not_wildcard_import_api_services() -> None:
    violations: list[str] = []

    for file_path in ENDPOINTS_DIR.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module_name = node.module or ""
            imports_wildcard = any(alias.name == "*" for alias in node.names)
            if module_name.startswith("app.services.") and module_name.endswith(
                "_api_service"
            ) and imports_wildcard:
                violations.append(
                    f"{file_path.relative_to(BACKEND_ROOT)}:{node.lineno} -> {module_name}"
                )

    if violations:
        pytest.fail(
            "Endpoint shim wildcard imports from *_api_service are not allowed:\n"
            + "\n".join(f"- {violation}" for violation in sorted(violations))
        )


def test_endpoint_router_modules_are_published_or_allowlisted() -> None:
    endpoint_router_modules = _endpoint_modules_exporting_router()
    published_modules = _published_endpoint_modules()
    unpublished_modules = endpoint_router_modules - published_modules

    unexpected_unpublished = unpublished_modules - _ALLOWED_UNPUBLISHED_ENDPOINT_ROUTERS
    stale_allowlist = _ALLOWED_UNPUBLISHED_ENDPOINT_ROUTERS - unpublished_modules

    if not unexpected_unpublished and not stale_allowlist:
        return

    messages = ["Endpoint router publication guard failed:"]
    if unexpected_unpublished:
        messages.append(
            "Unexpected unpublished endpoint routers: "
            + ", ".join(sorted(unexpected_unpublished))
        )
    if stale_allowlist:
        messages.append(
            "Stale unpublished-router allowlist entries: "
            + ", ".join(sorted(stale_allowlist))
        )
    pytest.fail("\n".join(messages))


def test_api_route_path_methods_do_not_duplicate_except_allowlist() -> None:
    from app.api.v1.api import api_router

    route_owners: dict[tuple[str, str], list[str]] = {}
    for route in api_router.routes:
        path = getattr(route, "path", "")
        methods = (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}
        endpoint = getattr(route, "endpoint", None)
        module_name = getattr(endpoint, "__module__", "") if endpoint else ""
        endpoint_name = getattr(endpoint, "__name__", "") if endpoint else ""
        owner = f"{module_name}.{endpoint_name}"

        for method in methods:
            route_owners.setdefault((method, path), []).append(owner)

    duplicates = {
        key: owners for key, owners in route_owners.items() if len(owners) > 1
    }
    duplicate_keys = set(duplicates)
    unexpected_duplicates = duplicate_keys - _ALLOWED_DUPLICATE_API_ROUTE_METHODS
    stale_allowlist = _ALLOWED_DUPLICATE_API_ROUTE_METHODS - duplicate_keys

    if not unexpected_duplicates and not stale_allowlist:
        return

    messages = ["API route duplicate guard failed:"]
    if unexpected_duplicates:
        messages.append("Unexpected duplicate route registrations:")
        for method, path in sorted(unexpected_duplicates):
            owners = ", ".join(sorted(duplicates[(method, path)]))
            messages.append(f"- {method} {path}: {owners}")
    if stale_allowlist:
        messages.append(
            "Stale duplicate-route allowlist entries: "
            + ", ".join(
                f"{method} {path}" for method, path in sorted(stale_allowlist)
            )
        )
    pytest.fail("\n".join(messages))
