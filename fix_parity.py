import re

with open("ops/scripts/build_frontend_backend_parity.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_parse_frontend = False

for line in lines:
    if line.startswith("def parse_frontend_route_roles("):
        in_parse_frontend = True
        new_lines.append(line)
        new_lines.append("    content = frontend_app_path.read_text(encoding=\"utf-8\")\n")
        new_lines.append("    # Support the old App.jsx format\n")
        new_lines.append("    pattern_app = re.compile(r\"<Route\\s+path=\\\"([^\\\"]+)\\\"[^>]*element=\\{<RequireAuth\\s+roles=\\{\\[([^\\]]*)\\]\\}\", re.DOTALL)\n")
        new_lines.append("    role_paths = {}\n")
        new_lines.append("    for match in pattern_app.finditer(content):\n")
        new_lines.append("        path = _normalize_route_path(match.group(1))\n")
        new_lines.append("        roles_str = match.group(2)\n")
        new_lines.append("        role_matches = re.findall(r\"['\\\"]([^'\\\"]+)['\\\"]\", roles_str)\n")
        new_lines.append("        for role in role_matches:\n")
        new_lines.append("            role_paths.setdefault(role, []).append(path)\n")
        new_lines.append("\n")
        new_lines.append("    # Support the new routeRegistry.js format\n")
        new_lines.append("    pattern_registry = re.compile(r\"path:\\s*['\\\"]([^'\\\"]+)['\\\"],[\\s\\S]*?roles:\\s*\\[([^\\]]*)\\]\")\n")
        new_lines.append("    for match in pattern_registry.finditer(content):\n")
        new_lines.append("        path = _normalize_route_path(match.group(1))\n")
        new_lines.append("        roles_str = match.group(2)\n")
        new_lines.append("        role_matches = re.findall(r\"['\\\"]([^'\\\"]+)['\\\"]\", roles_str)\n")
        new_lines.append("        for role in role_matches:\n")
        new_lines.append("            role_paths.setdefault(role, []).append(path)\n")
        new_lines.append("\n")
        new_lines.append("    # Also scan routeRegistry.js if the given file is App.jsx\n")
        new_lines.append("    registry_path = frontend_app_path.parent / \"routing\" / \"routeRegistry.js\"\n")
        new_lines.append("    if registry_path.exists():\n")
        new_lines.append("        registry_content = registry_path.read_text(encoding=\"utf-8\")\n")
        new_lines.append("        for match in pattern_registry.finditer(registry_content):\n")
        new_lines.append("            path = _normalize_route_path(match.group(1))\n")
        new_lines.append("            roles_str = match.group(2)\n")
        new_lines.append("            role_matches = re.findall(r\"['\\\"]([^'\\\"]+)['\\\"]\", roles_str)\n")
        new_lines.append("            for role in role_matches:\n")
        new_lines.append("                role_paths.setdefault(role, []).append(path)\n")
        new_lines.append("\n")
        new_lines.append("    LOGGER.info(\"frontend_backend_parity.frontend_roles_loaded file=%s roles=%d\", frontend_app_path.name, len(role_paths))\n")
        new_lines.append("    return role_paths\n")
        continue

    if in_parse_frontend:
        if line.startswith("def ") or line.startswith("class "):
            in_parse_frontend = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("ops/scripts/build_frontend_backend_parity.py", "w") as f:
    f.writelines(new_lines)
