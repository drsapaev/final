from __future__ import annotations

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
