from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "ops" / "scripts" / "build_frontend_backend_parity.py"
    spec = importlib.util.spec_from_file_location("build_frontend_backend_parity", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load build_frontend_backend_parity.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_parse_api_endpoints_constants_supports_function_aliases():
    module = _load_module()
    root = Path(__file__).resolve().parents[3]
    constants = module.parse_api_endpoints_constants(root / "frontend" / "src" / "api" / "endpoints.js")

    assert constants["USERS.LIST"] == "/users"
    assert constants["USERS.GET"] == "/users/{id}"
    assert constants["DOCTORS.SCHEDULE"] == "/doctors/{id}/schedule"
    assert constants["QUEUE.COMPLETE"] == "/queue/{id}/complete"


@pytest.mark.unit
def test_build_parity_resolves_api_endpoints_function_reference():
    module = _load_module()
    backend_ops = [
        module.BackendOperation(
            path="/api/v1/users/{id}",
            method="GET",
            operation_id="get_user",
        )
    ]
    frontend_calls = [
        {
            "file": "frontend/src/api/services.js",
            "line": 58,
            "method": "GET",
            "endpoint_expr": "API_ENDPOINTS.USERS.GET(id)",
        }
    ]
    constants = {"USERS.GET": "/users/{id}"}

    parity = module.build_parity(backend_ops, frontend_calls, constants)
    assert parity["summary"]["implemented"] == 1
    assert parity["summary"]["partial"] == 0
    assert parity["summary"]["frontend_orphan"] == 0
    assert parity["summary"]["missing_in_frontend"] == 0


@pytest.mark.unit
def test_rbac_alignment_matches_backend_surface():
    module = _load_module()
    root = Path(__file__).resolve().parents[3]
    frontend_role_paths = module.parse_frontend_route_roles(root / "frontend" / "src" / "App.jsx")
    rbac = module.evaluate_rbac_alignment(frontend_role_paths)

    assert rbac["status"] == "pass"
    assert rbac["frontend_only_roles"] == []
    assert rbac["backend_only_roles"] == []
    assert rbac["route_mismatches"] == []
