#!/usr/bin/env python3
"""
Генерация OpenAPI схемы для системы управления клиникой
"""
import json
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

def generate_openapi_schema():
    """Генерирует OpenAPI схему и выводит её в JSON формате"""
    try:
        # Получаем OpenAPI схему из FastAPI приложения
        openapi_schema = app.openapi()
        
        # Выводим схему в JSON формате
        print(json.dumps(openapi_schema, indent=2, ensure_ascii=False))
        
        return True
    except Exception as e:
        print(f"Ошибка генерации OpenAPI схемы: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = generate_openapi_schema()
    sys.exit(0 if success else 1)
