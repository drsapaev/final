#!/usr/bin/env python3
"""Build frontend-backend API parity matrix from OpenAPI + frontend usage inventory."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("frontend_backend_parity")
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
CRITICAL_PREFIXES = ["/api/v1/auth", "/api/v1/queue", "/api/v1/billing", "/api/v1/emr"]
CONST_TOKEN_PATTERN = re.compile(r"API_ENDPOINTS((?:\.[A-Z_]+)+)")
PARAM_PATTERN = re.compile(r"\{[^/]+\}")
PATH_FRAGMENT_PATTERN = re.compile(r"/[A-Za-z0-9_{}./-]+")
TEMPLATE_EXPR_PATTERN = re.compile(r"\$\{([^{}]+)\}")
ROLE_LITERAL_PATTERN = re.compile(r"'([^']+)'|\"([^\"]+)\"")

CRITICAL_FLOW_SPECS = [
    {
        "id": "registrar_queue",
        "name": "Registrar Queue",
        "requirements": [
            ("POST", "/api/v1/queue/join/start"),
            ("POST", "/api/v1/queue/join/complete"),
            ("GET", "/api/v1/registrar/queues/today"),
            ("POST", "/api/v1/registrar/open-reception"),
            ("POST", "/api/v1/queue/{specialist_id}/call-next"),
        ],
    },
    {
        "id": "doctor_emr_rw",
        "name": "Doctor EMR Read/Write",
        "requirements": [
            ("GET", "/api/v1/emr/templates"),
            ("GET", "/api/v1/emr/doctor-templates/treatment"),
            ("PUT", "/api/v1/emr/doctor-templates/treatment/{template_id}"),
            ("POST", "/api/v1/emr/phrase-index"),
            ("POST", "/api/v1/emr/telemetry"),
        ],
    },
    {
        "id": "cashier_payment",
        "name": "Cashier Payment Status/Receipt",
        "requirements": [
            ("GET", "/api/v1/cashier/payments/{payment_id}"),
            ("POST", "/api/v1/cashier/payments/{payment_id}/cancel"),
            ("POST", "/api/v1/cashier/payments/{payment_id}/confirm"),
            ("GET", "/api/v1/cashier/payments/{payment_id}/receipt"),
            ("GET", "/api/v1/payments/{payment_id}/receipt/download"),
        ],
    },
    {
        "id": "admin_settings",
        "name": "Admin Settings",
        "requirements": [
            ("GET", "/api/v1/admin/wizard-settings"),
            ("POST", "/api/v1/admin/wizard-settings"),
            ("GET", "/api/v1/admin/benefit-settings"),
            ("POST", "/api/v1/admin/benefit-settings"),
            ("GET", "/api/v1/admin/payment-provider-settings"),
            ("POST", "/api/v1/admin/payment-provider-settings"),
            ("GET", "/api/v1/admin/clinic/settings"),
            ("PUT", "/api/v1/admin/clinic/settings"),
        ],
    },
]


@dataclass(slots=True)
class BackendOperation:
    path: str
    method: str
    operation_id: str

    @property
    def normalized_path(self) -> str:
        return normalize_param_path(normalize_path(self.path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create frontend-backend parity report.")
    parser.add_argument(
        "--openapi",
        type=Path,
        default=Path("backend/openapi.json"),
        help="Backend OpenAPI snapshot path.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("docs/reports/frontend_api_usage_inventory.json"),
        help="Frontend API usage inventory JSON.",
    )
    parser.add_argument(
        "--endpoints-js",
        type=Path,
        default=Path("frontend/src/api/endpoints.js"),
        help="Path to API_ENDPOINTS JS source.",
    )
    parser.add_argument(
        "--frontend-app",
        type=Path,
        default=Path("frontend/src/App.jsx"),
        help="Path to frontend app routes for RBAC alignment.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("docs/reports/frontend_backend_parity.json"),
        help="Parity matrix JSON output path.",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=Path("docs/reports/FRONTEND_BACKEND_PARITY_REPORT.md"),
        help="Parity report markdown output path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def normalize_path(path: str) -> str:
    clean = path.strip()
    if not clean:
        return clean
    if "?" in clean:
        clean = clean.split("?", 1)[0]
    if not clean.startswith("/api/v1"):
        clean = f"/api/v1{clean if clean.startswith('/') else '/' + clean}"
    if clean != "/" and clean.endswith("/"):
        clean = clean[:-1]
    return clean


def normalize_param_path(path: str) -> str:
    return PARAM_PATTERN.sub("{}", path)


def parse_openapi_operations(openapi_path: Path) -> list[BackendOperation]:
    data = json.loads(openapi_path.read_text(encoding="utf-8"))
    operations: list[BackendOperation] = []
    for path, item in data.get("paths", {}).items():
        for method_name, operation in item.items():
            method = method_name.lower()
            if method not in HTTP_METHODS:
                continue
            operation_id = ""
            if isinstance(operation, dict):
                operation_id = operation.get("operationId", "")
            operations.append(
                BackendOperation(
                    path=normalize_path(path),
                    method=method.upper(),
                    operation_id=operation_id,
                )
            )
    LOGGER.info(
        "frontend_backend_parity.openapi_loaded file=%s operations=%d",
        openapi_path.as_posix(),
        len(operations),
    )
    return operations


def parse_api_endpoints_constants(endpoints_js_path: Path) -> dict[str, str]:
    content = endpoints_js_path.read_text(encoding="utf-8")
    start_token = "export const API_ENDPOINTS = {"
    start = content.find(start_token)
    if start < 0:
        return {}
    block_start = content.find("{", start)
    if block_start < 0:
        return {}

    depth = 0
    block_end = -1
    for idx in range(block_start, len(content)):
        char = content[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                block_end = idx
                break
    if block_end < 0:
        return {}

    body = content[block_start + 1 : block_end]
    stack: list[str] = []
    mapping: dict[str, str] = {}

    object_open_pattern = re.compile(r"^\s*([A-Z_]+)\s*:\s*\{\s*$")
    value_pattern = re.compile(r"^\s*([A-Z_]+)\s*:\s*['\"]([^'\"]+)['\"]\s*,?\s*$")
    function_template_pattern = re.compile(
        r"^\s*([A-Z_]+)\s*:\s*\([^)]*\)\s*=>\s*`([^`]+)`\s*,?\s*$"
    )
    function_quote_pattern = re.compile(
        r"^\s*([A-Z_]+)\s*:\s*\([^)]*\)\s*=>\s*['\"]([^'\"]+)['\"]\s*,?\s*$"
    )

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("}"):
            if stack:
                stack.pop()
            continue

        match_open = object_open_pattern.match(raw_line)
        if match_open:
            stack.append(match_open.group(1))
            continue

        match_value = value_pattern.match(raw_line)
        if match_value:
            key = ".".join(stack + [match_value.group(1)])
            mapping[key] = match_value.group(2)
            continue

        match_function = function_template_pattern.match(raw_line) or function_quote_pattern.match(raw_line)
        if match_function:
            key = ".".join(stack + [match_function.group(1)])
            template = re.sub(r"\$\{([^}]+)\}", r"{\1}", match_function.group(2))
            mapping[key] = template
            continue

    LOGGER.info(
        "frontend_backend_parity.constants_loaded file=%s constants=%d",
        endpoints_js_path.as_posix(),
        len(mapping),
    )
    return mapping


def replace_constant_tokens(expr: str, constants: dict[str, str]) -> tuple[str, bool]:
    unresolved_found = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal unresolved_found
        key = match.group(1).lstrip(".")
        value = constants.get(key)
        if value is None:
            unresolved_found = True
            return match.group(0)
        return value

    replaced = CONST_TOKEN_PATTERN.sub(_replace, expr)
    return replaced, unresolved_found


def try_resolve_frontend_path(endpoint_expr: str, constants: dict[str, str]) -> tuple[str | None, str]:
    expr = endpoint_expr.strip()

    unresolved_template = False

    def _replace_template_expr(match: re.Match[str]) -> str:
        nonlocal unresolved_template
        inner = match.group(1).strip()
        replaced_inner, unresolved_const_inner = replace_constant_tokens(inner, constants)
        fragment_match = PATH_FRAGMENT_PATTERN.search(replaced_inner)
        if fragment_match:
            return fragment_match.group(0)
        unresolved_template = unresolved_template or unresolved_const_inner
        return "{param}"

    expr_with_templates = TEMPLATE_EXPR_PATTERN.sub(_replace_template_expr, expr)
    replaced, unresolved_const = replace_constant_tokens(expr_with_templates, constants)
    unresolved_const = unresolved_const or unresolved_template

    for fragment in PATH_FRAGMENT_PATTERN.findall(replaced):
        candidate = normalize_path(fragment)
        if not candidate:
            continue
        return candidate, "resolved_with_constants" if "API_ENDPOINTS" in expr else "resolved_literal"

    if unresolved_const:
        return None, "unresolved_constant_ref"
    if "${" in expr or "+" in expr:
        return None, "dynamic_expression"
    return None, "unresolved_expression"


def load_frontend_calls(inventory_path: Path) -> list[dict]:
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    calls = data.get("calls", [])
    LOGGER.info(
        "frontend_backend_parity.inventory_loaded file=%s calls=%d",
        inventory_path.as_posix(),
        len(calls),
    )
    return calls


def build_parity(
    backend_ops: list[BackendOperation],
    frontend_calls: list[dict],
    constants: dict[str, str],
) -> dict:
    backend_by_key: dict[tuple[str, str], list[BackendOperation]] = defaultdict(list)
    for op in backend_ops:
        backend_by_key[(op.method, op.normalized_path)].append(op)

    matched_backend_keys: set[tuple[str, str]] = set()
    frontend_orphan: list[dict] = []
    partial: list[dict] = []
    implemented: list[dict] = []
    resolved_frontend_calls: list[dict] = []

    for call in frontend_calls:
        method = str(call.get("method", "")).upper()
        endpoint_expr = str(call.get("endpoint_expr", "")).strip()
        resolved_path, resolution = try_resolve_frontend_path(endpoint_expr, constants)

        if not resolved_path:
            partial.append(
                {
                    "file": call.get("file"),
                    "line": call.get("line"),
                    "method": method,
                    "endpoint_expr": endpoint_expr,
                    "reason": resolution,
                }
            )
            continue

        normalized = normalize_param_path(resolved_path)
        key = (method, normalized)
        matched_ops = backend_by_key.get(key, [])
        resolved_call = {
            "method": method,
            "path": resolved_path,
            "normalized_path": normalized,
            "file": call.get("file"),
            "line": call.get("line"),
            "endpoint_expr": endpoint_expr,
            "resolution": resolution,
            "backend_match": bool(matched_ops),
        }
        resolved_frontend_calls.append(resolved_call)

        if matched_ops:
            matched_backend_keys.add(key)
            implemented.append(
                {
                    **resolved_call,
                    "operation_ids": [op.operation_id for op in matched_ops if op.operation_id],
                }
            )
            continue

        frontend_orphan.append(
            {
                "file": call.get("file"),
                "line": call.get("line"),
                "method": method,
                "resolved_path": resolved_path,
                "normalized_path": normalized,
                "endpoint_expr": endpoint_expr,
                "reason": "no_backend_match",
            }
        )

    missing_in_frontend: list[dict] = []
    for op in backend_ops:
        key = (op.method, op.normalized_path)
        if key in matched_backend_keys:
            continue
        missing_in_frontend.append(
            {
                "method": op.method,
                "path": op.path,
                "normalized_path": op.normalized_path,
                "operation_id": op.operation_id,
            }
        )

    summary = {
        "backend_operations_total": len(backend_ops),
        "frontend_calls_total": len(frontend_calls),
        "implemented": len(implemented),
        "partial": len(partial),
        "missing_in_frontend": len(missing_in_frontend),
        "frontend_orphan": len(frontend_orphan),
    }
    if summary["backend_operations_total"] > 0:
        summary["coverage_pct"] = round(
            (summary["implemented"] / summary["backend_operations_total"]) * 100,
            2,
        )
    else:
        summary["coverage_pct"] = 0.0

    return {
        "summary": summary,
        "implemented": implemented,
        "partial": partial,
        "missing_in_frontend": missing_in_frontend,
        "frontend_orphan": frontend_orphan,
        "resolved_frontend_calls": resolved_frontend_calls,
        "backend_by_key": backend_by_key,
    }


def critical_missing_stats(missing_in_frontend: list[dict]) -> dict[str, int]:
    stats = {prefix: 0 for prefix in CRITICAL_PREFIXES}
    for item in missing_in_frontend:
        path = str(item.get("path", ""))
        for prefix in CRITICAL_PREFIXES:
            if path.startswith(prefix):
                stats[prefix] += 1
    return stats


def evaluate_critical_flows(parity: dict) -> dict:
    backend_by_key: dict[tuple[str, str], list[BackendOperation]] = parity["backend_by_key"]
    frontend_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for call in parity["resolved_frontend_calls"]:
        key = (call["method"], call["normalized_path"])
        frontend_by_key[key].append(call)

    flows: list[dict] = []
    for spec in CRITICAL_FLOW_SPECS:
        checks: list[dict] = []
        mismatches: list[dict] = []

        for method, path in spec["requirements"]:
            normalized = normalize_param_path(normalize_path(path))
            key = (method, normalized)
            backend_present = key in backend_by_key
            frontend_calls = frontend_by_key.get(key, [])
            frontend_present = len(frontend_calls) > 0

            if backend_present and frontend_present:
                status = "pass"
            elif not backend_present:
                status = "backend_missing"
                mismatches.append({"method": method, "path": path, "reason": status})
            else:
                status = "frontend_missing"
                mismatches.append({"method": method, "path": path, "reason": status})

            checks.append(
                {
                    "method": method,
                    "path": path,
                    "normalized_path": normalized,
                    "backend_present": backend_present,
                    "frontend_present": frontend_present,
                    "status": status,
                    "frontend_sources": [
                        f"{call['file']}:{call['line']}" for call in frontend_calls[:5]
                    ],
                }
            )

            if status != "pass":
                LOGGER.error(
                    "frontend_backend_parity.flow_mismatch flow=%s method=%s path=%s reason=%s",
                    spec["id"],
                    method,
                    path,
                    status,
                )

        passed = sum(1 for item in checks if item["status"] == "pass")
        flow_status = "pass" if passed == len(checks) else "fail"
        LOGGER.info(
            "frontend_backend_parity.flow_status flow=%s status=%s passed=%d required=%d",
            spec["id"],
            flow_status,
            passed,
            len(checks),
        )
        flows.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "status": flow_status,
                "passed_checks": passed,
                "total_checks": len(checks),
                "checks": checks,
                "mismatches": mismatches,
            }
        )

    summary = {
        "total_flows": len(flows),
        "passed_flows": sum(1 for flow in flows if flow["status"] == "pass"),
        "failed_flows": sum(1 for flow in flows if flow["status"] != "pass"),
    }
    return {"summary": summary, "flows": flows}


def _normalize_route_path(path: str) -> str:
    if not path:
        return "/"
    if path.startswith("/"):
        return path
    return f"/{path}"


def parse_frontend_route_roles(frontend_app_path: Path) -> dict[str, list[str]]:
    content = frontend_app_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<Route\s+path=\"(?P<path>[^\"]+)\"[^>]*element=\{<RequireAuth\s+roles=\{\[(?P<roles>[^\]]*)\]\}",
        re.DOTALL,
    )

    role_to_paths: dict[str, set[str]] = defaultdict(set)
    for match in pattern.finditer(content):
        route_path = _normalize_route_path(match.group("path").strip())
        role_block = match.group("roles")
        roles = [
            candidate.strip()
            for group in ROLE_LITERAL_PATTERN.findall(role_block)
            for candidate in group
            if candidate.strip()
        ]
        for role in roles:
            role_to_paths[role].add(route_path)

    output = {role: sorted(paths) for role, paths in role_to_paths.items()}
    LOGGER.info(
        "frontend_backend_parity.frontend_roles_loaded file=%s roles=%d",
        frontend_app_path.as_posix(),
        len(output),
    )
    return output


def load_backend_role_surface() -> tuple[set[str], dict[str, str]]:
    role_validation_path = Path("backend/app/core/role_validation.py")
    spec = importlib.util.spec_from_file_location("parity_role_validation", role_validation_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load role validation module: {role_validation_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    roles = set(str(role) for role in module.CRITICAL_ROLES)
    role_routes = {str(role): str(route) for role, route in module.ROLE_ROUTES.items()}
    LOGGER.info(
        "frontend_backend_parity.backend_roles_loaded roles=%d routes=%d",
        len(roles),
        len(role_routes),
    )
    return roles, role_routes


def evaluate_rbac_alignment(frontend_role_paths: dict[str, list[str]]) -> dict:
    backend_roles, backend_role_routes = load_backend_role_surface()
    frontend_roles = set(frontend_role_paths.keys())

    frontend_roles_lower = {role.lower(): role for role in frontend_roles}
    backend_roles_lower = {role.lower(): role for role in backend_roles}

    frontend_only = sorted(
        frontend_roles,
        key=lambda value: value.lower(),
    )
    frontend_only = [
        role for role in frontend_only if role.lower() not in backend_roles_lower
    ]
    backend_only = sorted(
        backend_roles,
        key=lambda value: value.lower(),
    )
    backend_only = [
        role for role in backend_only if role.lower() not in frontend_roles_lower
    ]

    route_checks: list[dict] = []
    route_mismatches: list[dict] = []
    for backend_role, expected_route in sorted(backend_role_routes.items()):
        normalized_expected = _normalize_route_path(expected_route)
        frontend_role = frontend_roles_lower.get(backend_role.lower())
        frontend_paths = frontend_role_paths.get(frontend_role, []) if frontend_role else []
        matched = normalized_expected in frontend_paths
        check = {
            "role": backend_role,
            "expected_route": normalized_expected,
            "frontend_role_found": bool(frontend_role),
            "frontend_role_name": frontend_role,
            "frontend_paths": frontend_paths,
            "matched": matched,
        }
        route_checks.append(check)
        if not matched:
            route_mismatches.append(
                {
                    "role": backend_role,
                    "expected_route": normalized_expected,
                    "frontend_paths": frontend_paths,
                }
            )
            LOGGER.warning(
                "frontend_backend_parity.rbac_route_mismatch role=%s expected_route=%s frontend_paths=%s",
                backend_role,
                normalized_expected,
                frontend_paths,
            )

    status = "pass"
    if frontend_only or backend_only or route_mismatches:
        status = "fail"

    LOGGER.info(
        "frontend_backend_parity.rbac_alignment status=%s frontend_only=%d backend_only=%d route_mismatches=%d",
        status,
        len(frontend_only),
        len(backend_only),
        len(route_mismatches),
    )

    return {
        "status": status,
        "summary": {
            "frontend_roles_total": len(frontend_roles),
            "backend_roles_total": len(backend_roles),
            "frontend_only_roles": len(frontend_only),
            "backend_only_roles": len(backend_only),
            "route_mismatches": len(route_mismatches),
        },
        "frontend_only_roles": frontend_only,
        "backend_only_roles": backend_only,
        "route_checks": route_checks,
        "route_mismatches": route_mismatches,
    }


def build_markdown_report(
    parity: dict,
    missing_stats: dict[str, int],
    critical_flows: dict,
    rbac_alignment: dict,
) -> str:
    summary = parity["summary"]
    lines: list[str] = []
    lines.append("# Frontend-Backend Parity Report")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Backend operations total: **{summary['backend_operations_total']}**")
    lines.append(f"- Frontend calls total: **{summary['frontend_calls_total']}**")
    lines.append(f"- Implemented matches: **{summary['implemented']}**")
    lines.append(f"- Partial (unresolved frontend calls): **{summary['partial']}**")
    lines.append(f"- Missing in frontend: **{summary['missing_in_frontend']}**")
    lines.append(f"- Frontend orphan calls: **{summary['frontend_orphan']}**")
    lines.append(f"- Coverage: **{summary['coverage_pct']}%**")
    lines.append("")
    lines.append("## Critical Missing (auth/queue/billing/emr)")
    lines.append("")
    for prefix, count in missing_stats.items():
        lines.append(f"- `{prefix}`: **{count}** missing operations")
    lines.append("")
    lines.append("## Critical Flows")
    lines.append("")
    lines.append(
        f"- Passed: **{critical_flows['summary']['passed_flows']}** / "
        f"**{critical_flows['summary']['total_flows']}**"
    )
    lines.append("")
    for flow in critical_flows["flows"]:
        lines.append(
            f"- `{flow['id']}` ({flow['name']}): **{flow['status']}** "
            f"({flow['passed_checks']}/{flow['total_checks']})"
        )
    lines.append("")
    lines.append("## RBAC Alignment")
    lines.append("")
    lines.append(f"- Status: **{rbac_alignment['status']}**")
    lines.append(
        f"- Frontend-only roles: **{rbac_alignment['summary']['frontend_only_roles']}**"
    )
    lines.append(
        f"- Backend-only roles: **{rbac_alignment['summary']['backend_only_roles']}**"
    )
    lines.append(
        f"- Route mismatches: **{rbac_alignment['summary']['route_mismatches']}**"
    )
    if rbac_alignment["frontend_only_roles"]:
        lines.append(
            "- Frontend-only role names: "
            + ", ".join(f"`{role}`" for role in rbac_alignment["frontend_only_roles"])
        )
    if rbac_alignment["backend_only_roles"]:
        lines.append(
            "- Backend-only role names: "
            + ", ".join(f"`{role}`" for role in rbac_alignment["backend_only_roles"])
        )
    lines.append("")

    partial_preview = parity["partial"][:40]
    orphan_preview = parity["frontend_orphan"][:40]
    lines.append("## Partial Preview (first 40)")
    lines.append("")
    for item in partial_preview:
        lines.append(
            f"- `{item['method']}` `{item['endpoint_expr']}` "
            f"({item['file']}:{item['line']}) reason=`{item['reason']}`"
        )
    lines.append("")
    lines.append("## Frontend Orphan Preview (first 40)")
    lines.append("")
    for item in orphan_preview:
        lines.append(
            f"- `{item['method']}` `{item['resolved_path']}` "
            f"({item['file']}:{item['line']})"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    LOGGER.info("frontend_backend_parity.start")

    backend_ops = parse_openapi_operations(args.openapi)
    frontend_calls = load_frontend_calls(args.inventory)
    constants = parse_api_endpoints_constants(args.endpoints_js)
    parity = build_parity(backend_ops, frontend_calls, constants)
    missing_stats = critical_missing_stats(parity["missing_in_frontend"])
    critical_flows = evaluate_critical_flows(parity)
    frontend_role_paths = parse_frontend_route_roles(args.frontend_app)
    rbac_alignment = evaluate_rbac_alignment(frontend_role_paths)

    for prefix, count in missing_stats.items():
        if count > 0:
            LOGGER.warning(
                "frontend_backend_parity.critical_missing prefix=%s count=%d",
                prefix,
                count,
            )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "openapi": args.openapi.as_posix(),
            "inventory": args.inventory.as_posix(),
            "endpoints_js": args.endpoints_js.as_posix(),
        },
        "summary": parity["summary"],
        "critical_missing": missing_stats,
        "critical_flows": critical_flows,
        "rbac_alignment": rbac_alignment,
        "implemented": parity["implemented"],
        "partial": parity["partial"],
        "missing_in_frontend": parity["missing_in_frontend"],
        "frontend_orphan": parity["frontend_orphan"],
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    markdown = build_markdown_report(parity, missing_stats, critical_flows, rbac_alignment)
    args.report_md.write_text(markdown, encoding="utf-8")

    LOGGER.info(
        "frontend_backend_parity.done coverage_pct=%.2f implemented=%d partial=%d missing=%d orphan=%d",
        parity["summary"]["coverage_pct"],
        parity["summary"]["implemented"],
        parity["summary"]["partial"],
        parity["summary"]["missing_in_frontend"],
        parity["summary"]["frontend_orphan"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
