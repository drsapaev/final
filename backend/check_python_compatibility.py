#!/usr/bin/env python3
"""
Проверка совместимости зависимостей с Python 3.11.10
"""
import subprocess
import sys
import os

def check_python_version():
    """Проверяем версию Python"""
    print(f"🐍 Текущая версия Python: {sys.version}")
    if sys.version_info.major == 3 and sys.version_info.minor == 11:
        print("✅ Python 3.11 - совместимая версия")
        return True
    else:
        print(f"⚠️  Python {sys.version_info.major}.{sys.version_info.minor} - может быть несовместим")
        return False

def check_requirements():
    """Проверяем файл requirements.txt"""
    print("\n📋 Проверяем requirements.txt...")
    
    # Проверяем в текущей директории и в родительской
    req_paths = ["requirements.txt", "../requirements.txt"]
    req_path = None
    
    for path in req_paths:
        if os.path.exists(path):
            req_path = path
            break
    
    if not req_path:
        print("❌ Файл requirements.txt не найден")
        return False
    
    with open(req_path, "r") as f:
        requirements = f.read().strip().split("\n")
    
    print(f"📦 Найдено {len(requirements)} зависимостей")
    
    # Проверяем критические зависимости
    critical_deps = [
        "fastapi",
        "uvicorn", 
        "sqlalchemy",
        "alembic",
        "pydantic",
        "python-multipart",
        "python-jose",
        "passlib",
        "argon2-cffi"
    ]
    
    found_deps = []
    for req in requirements:
        if req.strip() and not req.startswith("#"):
            dep_name = req.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
            if dep_name.lower() in critical_deps:
                found_deps.append(dep_name)
    
    print(f"✅ Найдено критических зависимостей: {len(found_deps)}/{len(critical_deps)}")
    for dep in found_deps:
        print(f"  - {dep}")
    
    missing_deps = set(critical_deps) - set(found_deps)
    if missing_deps:
        print(f"⚠️  Отсутствуют критические зависимости: {missing_deps}")
    
    return len(found_deps) >= len(critical_deps) * 0.8  # 80% критических зависимостей

def test_imports():
    """Тестируем импорт основных модулей"""
    print("\n🔍 Тестируем импорт модулей...")
    
    test_modules = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "pydantic",
        "passlib",
        "argon2"
    ]
    
    success_count = 0
    for module in test_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
        except Exception as e:
            print(f"  ⚠️  {module}: {e}")
    
    print(f"\n📊 Результат импорта: {success_count}/{len(test_modules)} модулей")
    return success_count >= len(test_modules) * 0.8

def check_docker_compatibility():
    """Проверяем совместимость с Docker"""
    print("\n🐳 Проверяем совместимость с Docker...")
    
    # Проверяем Dockerfile в разных местах
    dockerfile_paths = ["../ops/backend.Dockerfile", "ops/backend.Dockerfile", "../backend.Dockerfile"]
    dockerfile_path = None
    
    for path in dockerfile_paths:
        if os.path.exists(path):
            dockerfile_path = path
            break
    
    if not dockerfile_path:
        print("❌ Dockerfile не найден")
        return False
    
    with open(dockerfile_path, "r") as f:
        content = f.read()
    
    if "python:3.11.10-slim" in content:
        print("✅ Dockerfile использует стабильную версию Python 3.11.10")
        return True
    elif "python:3.14" in content:
        print("❌ Dockerfile использует нестабильную версию Python 3.14")
        return False
    else:
        print("⚠️  Dockerfile использует другую версию Python")
        return False

def main():
    """Основная функция проверки"""
    print("🚀 Проверка совместимости зависимостей")
    print("=" * 50)
    
    checks = [
        ("Версия Python", check_python_version),
        ("Requirements.txt", check_requirements),
        ("Импорт модулей", test_imports),
        ("Docker совместимость", check_docker_compatibility)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        try:
            if check_func():
                passed += 1
                print(f"✅ {name}: ПРОШЕЛ")
            else:
                print(f"❌ {name}: НЕ ПРОШЕЛ")
        except Exception as e:
            print(f"❌ {name}: ОШИБКА - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{total} проверок прошли")
    
    if passed == total:
        print("✅ Все проверки прошли успешно!")
        print("🎉 Система готова к работе с Python 3.11.10")
        return 0
    else:
        print("❌ Некоторые проверки не прошли")
        print("🔧 Рекомендуется исправить проблемы перед продолжением")
        return 1

if __name__ == "__main__":
    sys.exit(main())
