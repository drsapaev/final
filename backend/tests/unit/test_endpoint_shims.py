from __future__ import annotations

import ast
import re
from pathlib import Path


SHIM_IMPORT_RE = re.compile(
    r"from app\.services\.(?P<service_module>[a-z0-9_]+)_service import \*"
)


def _endpoint_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "endpoints"
    return sorted(p for p in root.glob("*.py") if p.name != "__init__.py")


def test_all_endpoints_are_compatibility_shims() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    for endpoint_file in _endpoint_files():
        text = endpoint_file.read_text(encoding="utf-8")
        assert "Compatibility shim for" in text, endpoint_file.name

        match = SHIM_IMPORT_RE.search(text)
        assert match is not None, endpoint_file.name

        expected_module = endpoint_file.stem
        service_module = match.group("service_module")
        assert service_module in {expected_module, f"{expected_module}_api"}, (
            endpoint_file.name
        )
        service_path = app_root / "services" / f"{service_module}_service.py"
        assert service_path.exists(), endpoint_file.name


def test_endpoint_shims_do_not_contain_runtime_logic() -> None:
    """Endpoint modules must stay as pure re-export shims."""
    for endpoint_file in _endpoint_files():
        tree = ast.parse(endpoint_file.read_text(encoding="utf-8"))
        nodes = [
            node
            for node in tree.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(getattr(node, "value", None), ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        assert len(nodes) == 1, endpoint_file.name

        only_node = nodes[0]
        assert isinstance(only_node, ast.ImportFrom), endpoint_file.name
        assert only_node.module and only_node.module.startswith("app.services."), (
            endpoint_file.name
        )
        assert len(only_node.names) == 1 and only_node.names[0].name == "*", (
            endpoint_file.name
        )
