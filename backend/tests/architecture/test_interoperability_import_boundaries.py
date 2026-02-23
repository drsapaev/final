from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
_FORBIDDEN_MODULE = "app.services.external_integration_service"


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
