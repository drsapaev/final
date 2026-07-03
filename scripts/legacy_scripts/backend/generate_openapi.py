#!/usr/bin/env python3
"""
Генерация OpenAPI схемы для системы управления клиникой
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
LOGGER = logging.getLogger("openapi_generator")


def _count_operations(openapi_schema: dict) -> int:
    paths = openapi_schema.get("paths", {})
    total = 0
    for path_item in paths.values():
        for method_name in path_item.keys():
            if method_name.lower() in HTTP_METHODS:
                total += 1
    return total


def generate_openapi_schema(output_path: Path, emit_stdout: bool = False) -> bool:
    """Генерирует OpenAPI схему и сохраняет её в JSON файл."""
    try:
        # Импорт приложения здесь, чтобы лог-конфиг уже был применен.
        from app.main import app

        LOGGER.info("openapi.generate.start output_path=%s", output_path)

        # Получаем OpenAPI схему из FastAPI приложения
        openapi_schema = app.openapi()
        path_count = len(openapi_schema.get("paths", {}))
        operation_count = _count_operations(openapi_schema)
        LOGGER.debug(
            "openapi.generate.stats paths=%d operations=%d",
            path_count,
            operation_count,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(openapi_schema, indent=2, ensure_ascii=False)
        output_path.write_text(payload, encoding="utf-8")

        if emit_stdout:
            print(payload)

        LOGGER.info(
            "openapi.generate.done output_path=%s bytes=%d paths=%d operations=%d",
            output_path,
            output_path.stat().st_size,
            path_count,
            operation_count,
        )
        return True
    except Exception:
        LOGGER.exception("openapi.generate.failed")
        return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OpenAPI snapshot for backend.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("openapi.json"),
        help="Path to output openapi.json file.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print generated OpenAPI JSON to stdout.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    success = generate_openapi_schema(output_path=args.output, emit_stdout=args.stdout)
    sys.exit(0 if success else 1)
