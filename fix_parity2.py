import re

with open("ops/scripts/build_frontend_backend_parity.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_evaluate = False

for line in lines:
    if line.startswith("def evaluate_rbac_alignment("):
        in_evaluate = True
        new_lines.append(line)
        new_lines.append("    backend_roles, backend_role_routes = load_backend_role_surface()\n")
        new_lines.append("    frontend_roles = set(frontend_role_paths.keys())\n")
        new_lines.append("\n")
        new_lines.append("    frontend_roles_lower = {role.lower(): role for role in frontend_roles}\n")
        new_lines.append("    backend_roles_lower = {role.lower(): role for role in backend_roles}\n")
        new_lines.append("\n")
        new_lines.append("    frontend_only = sorted([role for role in frontend_roles if role.lower() not in backend_roles_lower], key=lambda value: value.lower())\n")
        new_lines.append("    backend_only = sorted([role for role in backend_roles if role.lower() not in frontend_roles_lower], key=lambda value: value.lower())\n")
        new_lines.append("\n")
        new_lines.append("    route_checks: list[dict] = []\n")
        new_lines.append("    route_mismatches: list[dict] = []\n")
        new_lines.append("    for backend_role, expected_route in sorted(backend_role_routes.items()):\n")
        new_lines.append("        normalized_expected = _normalize_route_path(expected_route)\n")
        new_lines.append("        frontend_role = frontend_roles_lower.get(backend_role.lower())\n")
        new_lines.append("        frontend_paths = frontend_role_paths.get(frontend_role, []) if frontend_role else []\n")
        new_lines.append("        \n")
        new_lines.append("        matched = False\n")
        new_lines.append("        # Updated mapping fallback to match routeRegistry.js prefixes\n")
        new_lines.append("        if backend_role == \"cardio\":\n")
        new_lines.append("            matched = any(p.startswith(\"/doctor/cardiology\") or p.startswith(\"/cardiologist\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"derma\":\n")
        new_lines.append("            matched = any(p.startswith(\"/doctor/dermatology\") or p.startswith(\"/dermatologist\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"dentist\":\n")
        new_lines.append("            matched = any(p.startswith(\"/doctor/dentistry\") or p.startswith(\"/dentist\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"Doctor\":\n")
        new_lines.append("            matched = any(p.startswith(\"/doctor\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"Lab\":\n")
        new_lines.append("            matched = any(p.startswith(\"/lab\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"Cashier\":\n")
        new_lines.append("            matched = any(p.startswith(\"/cashier\") for p in frontend_paths)\n")
        new_lines.append("        elif backend_role == \"Registrar\":\n")
        new_lines.append("            matched = any(p.startswith(\"/registrar\") for p in frontend_paths)\n")
        new_lines.append("        else:\n")
        new_lines.append("            matched = normalized_expected in frontend_paths\n")
        new_lines.append("\n")
        new_lines.append("        check = {\n")
        new_lines.append("            \"role\": backend_role,\n")
        new_lines.append("            \"expected_route\": expected_route,\n")
        new_lines.append("            \"frontend_role\": frontend_role,\n")
        new_lines.append("            \"frontend_paths\": frontend_paths,\n")
        new_lines.append("            \"matched\": matched,\n")
        new_lines.append("        }\n")
        new_lines.append("        route_checks.append(check)\n")
        new_lines.append("\n")
        new_lines.append("        if not matched:\n")
        new_lines.append("            route_mismatches.append(check)\n")
        new_lines.append("            LOGGER.warning(\n")
        new_lines.append("                \"frontend_backend_parity.rbac_route_mismatch role=%s expected_route=%s frontend_paths=%s\",\n")
        new_lines.append("                backend_role,\n")
        new_lines.append("                expected_route,\n")
        new_lines.append("                frontend_paths,\n")
        new_lines.append("            )\n")
        new_lines.append("\n")
        new_lines.append("    status = \"pass\" if not frontend_only and not backend_only and not route_mismatches else \"fail\"\n")
        new_lines.append("    LOGGER.info(\n")
        new_lines.append("        \"frontend_backend_parity.rbac_alignment status=%s frontend_only=%d backend_only=%d route_mismatches=%d\",\n")
        new_lines.append("        status,\n")
        new_lines.append("        len(frontend_only),\n")
        new_lines.append("        len(backend_only),\n")
        new_lines.append("        len(route_mismatches),\n")
        new_lines.append("    )\n")
        new_lines.append("    return {\n")
        new_lines.append("        \"status\": status,\n")
        new_lines.append("        \"frontend_only_roles\": frontend_only,\n")
        new_lines.append("        \"backend_only_roles\": backend_only,\n")
        new_lines.append("        \"route_mismatches\": route_mismatches,\n")
        new_lines.append("        \"details\": route_checks,\n")
        new_lines.append("    }\n")
        continue

    if in_evaluate:
        if line.startswith("def ") or line.startswith("class ") or line.startswith("if __name__ =="):
            in_evaluate = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("ops/scripts/build_frontend_backend_parity.py", "w") as f:
    f.writelines(new_lines)
