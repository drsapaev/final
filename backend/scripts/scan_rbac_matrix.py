"""
Скрипт для сканирования всех API эндпоинтов и построения фактической RBAC-матрицы.

Использование:
    python scripts/scan_rbac_matrix.py > rbac_matrix_scan.txt
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Критичные ресурсы для сканирования
CRITICAL_ENDPOINTS = [
    "patients",
    "visits",
    "appointments",
    "payments",
    "emr",
    "files",
    "lab",
]

# Путь к эндпоинтам
ENDPOINTS_DIR = Path(__file__).parent.parent / "app" / "api" / "v1" / "endpoints"


def extract_endpoint_info(file_path: Path) -> List[Dict]:
    """Извлекает информацию об эндпоинтах из файла"""
    endpoints = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Ищем декораторы @router.get, @router.post, etc.
                decorators = []
                route_path = None
                method = None
                required_roles = None
                has_get_current_user = False
                has_require_roles = False
                has_manual_role_check = False
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            # @router.get("/path")
                            if decorator.func.attr in ["get", "post", "put", "patch", "delete"]:
                                method = decorator.func.attr.upper()
                                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                    route_path = decorator.args[0].value
                        
                        # Проверяем dependencies=[Depends(require_roles(...))]
                        for keyword in decorator.keywords:
                            if keyword.arg == "dependencies":
                                if isinstance(keyword.value, ast.List):
                                    for dep in keyword.value.elts:
                                        if isinstance(dep, ast.Call):
                                            if isinstance(dep.func, ast.Name) and dep.func.id == "Depends":
                                                if dep.args:
                                                    dep_arg = dep.args[0]
                                                    if isinstance(dep_arg, ast.Call):
                                                        if isinstance(dep_arg.func, ast.Name) and dep_arg.func.id == "require_roles":
                                                            has_require_roles = True
                                                            if dep_arg.args:
                                                                required_roles = [arg.value if isinstance(arg, ast.Constant) else str(arg) for arg in dep_arg.args]
                
                # Проверяем параметры функции
                for arg in node.args.args:
                    if arg.annotation:
                        # Проверяем Depends(get_current_user) или Depends(require_roles(...))
                        if isinstance(arg.annotation, ast.Call):
                            if isinstance(arg.annotation.func, ast.Name) and arg.annotation.func.id == "Depends":
                                if arg.annotation.args:
                                    dep_arg = arg.annotation.args[0]
                                    if isinstance(dep_arg, ast.Attribute):
                                        if dep_arg.attr == "get_current_user":
                                            has_get_current_user = True
                                    elif isinstance(dep_arg, ast.Call):
                                        if isinstance(dep_arg.func, ast.Name) and dep_arg.func.id == "require_roles":
                                            has_require_roles = True
                                            if dep_arg.args:
                                                required_roles = [arg.value if isinstance(arg, ast.Constant) else str(arg) for arg in dep_arg.args]
                
                # Проверяем тело функции на явные проверки ролей
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.If):
                        # if user.role != "Admin" или if current_user.role == ...
                        if isinstance(stmt.test, ast.Compare):
                            has_manual_role_check = True
                
                if method and route_path:
                    endpoints.append({
                        "file": file_path.name,
                        "function": node.name,
                        "method": method,
                        "path": route_path,
                        "has_get_current_user": has_get_current_user,
                        "has_require_roles": has_require_roles,
                        "required_roles": required_roles,
                        "has_manual_role_check": has_manual_role_check,
                    })
    
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    
    return endpoints


def scan_all_endpoints() -> Dict[str, List[Dict]]:
    """Сканирует все эндпоинты в критичных файлах"""
    results = {}
    
    for endpoint_name in CRITICAL_ENDPOINTS:
        file_path = ENDPOINTS_DIR / f"{endpoint_name}.py"
        if file_path.exists():
            results[endpoint_name] = extract_endpoint_info(file_path)
        else:
            # Пробуем найти файлы с похожими именами
            for f in ENDPOINTS_DIR.glob(f"*{endpoint_name}*.py"):
                if endpoint_name not in results:
                    results[endpoint_name] = []
                results[endpoint_name].extend(extract_endpoint_info(f))
    
    return results


def print_matrix(results: Dict[str, List[Dict]]):
    """Выводит матрицу в читаемом формате"""
    print("=" * 100)
    print("RBAC MATRIX SCAN RESULTS")
    print("=" * 100)
    print()
    
    for endpoint_name, endpoints in results.items():
        print(f"\n## {endpoint_name.upper()}")
        print("-" * 100)
        
        if not endpoints:
            print("  No endpoints found")
            continue
        
        for ep in endpoints:
            protection = []
            if ep["has_require_roles"]:
                protection.append(f"require_roles({', '.join(ep['required_roles'] or [])})")
            if ep["has_get_current_user"]:
                protection.append("get_current_user")
            if ep["has_manual_role_check"]:
                protection.append("manual_if_check")
            if not protection:
                protection.append("NO_PROTECTION")
            
            compliant = "YES" if ep["has_require_roles"] or (ep["has_get_current_user"] and not ep["has_manual_role_check"]) else "NO"
            
            print(f"  {ep['method']:6} {ep['path']:40} | {', '.join(protection):50} | {compliant}")
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    
    total = sum(len(eps) for eps in results.values())
    no_protection = sum(1 for eps in results.values() for ep in eps if not ep["has_require_roles"] and not ep["has_get_current_user"])
    manual_checks = sum(1 for eps in results.values() for ep in eps if ep["has_manual_role_check"])
    with_require_roles = sum(1 for eps in results.values() for ep in eps if ep["has_require_roles"])
    
    print(f"Total endpoints: {total}")
    print(f"No protection: {no_protection}")
    print(f"Manual role checks: {manual_checks}")
    print(f"Using require_roles: {with_require_roles}")
    print(f"Compliance rate: {(with_require_roles / total * 100) if total > 0 else 0:.1f}%")


if __name__ == "__main__":
    results = scan_all_endpoints()
    print_matrix(results)

