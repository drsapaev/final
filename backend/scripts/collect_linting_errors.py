#!/usr/bin/env python3
"""
Скрипт для сбора всех ошибок линтинга в единый отчет
Использование: python scripts/collect_linting_errors.py
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def run_command(cmd, cwd=None):
    """Запускает команду и возвращает результат"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def main():
    backend_dir = Path(__file__).parent.parent
    reports_dir = backend_dir / "quality-reports"
    reports_dir.mkdir(exist_ok=True)
    
    print("🔍 Собираем все ошибки линтинга...")
    print(f"📁 Директория: {backend_dir}")
    print(f"📊 Отчеты будут сохранены в: {reports_dir}")
    print()
    
    errors = {
        "ruff": {"count": 0, "files": []},
        "flake8": {"count": 0, "output": ""},
        "mypy": {"count": 0, "output": ""},
        "pylint": {"count": 0, "output": ""},
    }
    
    # Ruff
    print("🔍 Проверяем Ruff...")
    for dir_name in ["app", "tests"]:
        dir_path = backend_dir / dir_name
        if dir_path.exists():
            cmd = f"ruff check {dir_name} --output-format=text"
            exit_code, stdout, stderr = run_command(cmd, cwd=backend_dir)
            report_file = reports_dir / f"ruff_{dir_name}.txt"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(stdout)
                if stderr:
                    f.write(f"\n--- stderr ---\n{stderr}")
            
            if exit_code != 0:
                error_lines = [l for l in stdout.split("\n") if l.strip()]
                errors["ruff"]["count"] += len(error_lines)
                errors["ruff"]["files"].append({
                    "dir": dir_name,
                    "errors": error_lines,
                    "file": str(report_file)
                })
                print(f"  ⚠️ {dir_name}: {len(error_lines)} ошибок")
            else:
                print(f"  ✅ {dir_name}: OK")
    
    # Flake8
    print("🔍 Проверяем Flake8...")
    if (backend_dir / "app").exists():
        cmd = "flake8 app --select=E9,F63,F7,F82 --show-source --statistics"
        exit_code, stdout, stderr = run_command(cmd, cwd=backend_dir)
        report_file = reports_dir / "flake8.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(stdout)
            if stderr:
                f.write(f"\n--- stderr ---\n{stderr}")
        
        if exit_code != 0:
            error_lines = [l for l in stdout.split("\n") if l.strip()]
            errors["flake8"]["count"] = len(error_lines)
            errors["flake8"]["output"] = stdout
            print(f"  ⚠️ Найдено: {len(error_lines)} критических ошибок")
        else:
            print("  ✅ Flake8: OK")
    
    # MyPy
    print("🔍 Проверяем MyPy...")
    if (backend_dir / "app").exists():
        cmd = "mypy app --ignore-missing-imports --show-error-codes"
        exit_code, stdout, stderr = run_command(cmd, cwd=backend_dir)
        report_file = reports_dir / "mypy.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(stdout)
            if stderr:
                f.write(f"\n--- stderr ---\n{stderr}")
        
        if exit_code != 0:
            error_lines = [l for l in stdout.split("\n") if "error:" in l]
            errors["mypy"]["count"] = len(error_lines)
            errors["mypy"]["output"] = stdout
            print(f"  ⚠️ Найдено: {len(error_lines)} ошибок типов")
        else:
            print("  ✅ MyPy: OK")
    
    # Pylint
    print("🔍 Проверяем Pylint...")
    if (backend_dir / "app").exists():
        cmd = "pylint app --disable=all --enable=E0602,E0603,E1120,E1121"
        exit_code, stdout, stderr = run_command(cmd, cwd=backend_dir)
        report_file = reports_dir / "pylint.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(stdout)
            if stderr:
                f.write(f"\n--- stderr ---\n{stderr}")
        
        if exit_code != 0:
            error_lines = [l for l in stdout.split("\n") if l.strip() and not l.startswith("---")]
            errors["pylint"]["count"] = len(error_lines)
            errors["pylint"]["output"] = stdout
            print(f"  ⚠️ Найдено: {len(error_lines)} ошибок")
        else:
            print("  ✅ Pylint: OK")
    
    # Создаем единый отчет
    print()
    print("📝 Создаю единый отчет...")
    
    total_errors = (
        errors["ruff"]["count"] +
        errors["flake8"]["count"] +
        errors["mypy"]["count"] +
        errors["pylint"]["count"]
    )
    
    report_file = reports_dir / "ALL_ERRORS_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Полный отчет об ошибках линтинга\n\n")
        f.write(f"Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Сводка\n\n")
        f.write(f"- **Ruff**: {errors['ruff']['count']} ошибок\n")
        f.write(f"- **Flake8**: {errors['flake8']['count']} критических ошибок\n")
        f.write(f"- **MyPy**: {errors['mypy']['count']} ошибок типов\n")
        f.write(f"- **Pylint**: {errors['pylint']['count']} ошибок\n")
        f.write(f"- **ВСЕГО: {total_errors} ошибок**\n\n")
        
        if errors["ruff"]["count"] > 0:
            f.write("## Ruff ошибки\n\n")
            for file_info in errors["ruff"]["files"]:
                f.write(f"### {file_info['dir']}/\n\n")
                f.write("```\n")
                f.write("\n".join(file_info["errors"][:100]))  # Первые 100 ошибок
                if len(file_info["errors"]) > 100:
                    f.write(f"\n... и еще {len(file_info['errors']) - 100} ошибок\n")
                f.write("```\n\n")
        
        if errors["flake8"]["count"] > 0:
            f.write("## Flake8 критические ошибки\n\n")
            f.write("```\n")
            f.write(errors["flake8"]["output"][:5000])  # Первые 5000 символов
            f.write("\n```\n\n")
        
        if errors["mypy"]["count"] > 0:
            f.write("## MyPy ошибки типов\n\n")
            f.write("```\n")
            f.write("\n".join(errors["mypy"]["output"].split("\n")[:200]))  # Первые 200 строк
            f.write("\n```\n\n")
        
        if errors["pylint"]["count"] > 0:
            f.write("## Pylint ошибки\n\n")
            f.write("```\n")
            f.write("\n".join(errors["pylint"]["output"].split("\n")[:100]))  # Первые 100 строк
            f.write("\n```\n\n")
        
        f.write("## Как исправить\n\n")
        f.write("1. Просмотрите отчет выше\n")
        f.write("2. Исправьте все ошибки\n")
        f.write("3. Запустите этот скрипт снова для проверки\n")
        f.write("4. После исправления всех ошибок закоммитьте изменения\n\n")
    
    print(f"✅ Отчет сохранен: {report_file}")
    print()
    print("📊 СВОДКА:")
    print(f"  Ruff: {errors['ruff']['count']} ошибок")
    print(f"  Flake8: {errors['flake8']['count']} критических ошибок")
    print(f"  MyPy: {errors['mypy']['count']} ошибок типов")
    print(f"  Pylint: {errors['pylint']['count']} ошибок")
    print(f"  ВСЕГО: {total_errors} ошибок")
    print()
    
    if total_errors > 0:
        print("⚠️ Найдены ошибки! Смотрите отчет выше.")
        print(f"📄 Полный отчет: {report_file}")
        return 1
    else:
        print("✅ Все проверки пройдены!")
        return 0

if __name__ == "__main__":
    sys.exit(main())

