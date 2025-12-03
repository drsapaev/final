#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аудит целостности внешних ключей и поиск orphaned records.
Проверяет все FK связи в базе данных и выводит отчет.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

import sqlalchemy as sa
from sqlalchemy import inspect, text

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_foreign_keys(conn, table_name: str) -> List[Dict]:
    """Получить все внешние ключи для таблицы"""
    inspector = inspect(conn)
    try:
        return inspector.get_foreign_keys(table_name)
    except Exception:
        return []


def check_orphaned_records(conn, child_table: str, fk_column: str, parent_table: str, parent_pk: str = "id") -> int:
    """Проверить количество orphaned записей"""
    try:
        query = text(f"""
            SELECT COUNT(*) as count
            FROM "{child_table}" c
            LEFT JOIN "{parent_table}" p ON c."{fk_column}" = p."{parent_pk}"
            WHERE c."{fk_column}" IS NOT NULL AND p."{parent_pk}" IS NULL
        """)
        result = conn.execute(query).fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"  ⚠️  Ошибка проверки {child_table}.{fk_column} -> {parent_table}.{parent_pk}: {e}")
        return -1


def audit_all_foreign_keys(conn) -> Dict[str, any]:
    """Аудит всех внешних ключей в базе данных"""
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    results = {
        "total_tables": len(tables),
        "tables_with_fks": 0,
        "total_fks": 0,
        "orphaned_records": [],
        "errors": []
    }
    
    print("=" * 80)
    print("АУДИТ ВНЕШНИХ КЛЮЧЕЙ И ORPHANED RECORDS")
    print("=" * 80)
    print()
    
    for table in tables:
        fks = get_foreign_keys(conn, table)
        if not fks:
            continue
        
        results["tables_with_fks"] += 1
        results["total_fks"] += len(fks)
        
        print(f"📋 Таблица: {table}")
        for fk in fks:
            fk_name = fk.get("name", "unnamed")
            constrained_columns = fk.get("constrained_columns", [])
            referred_table = fk.get("referred_table", "")
            referred_columns = fk.get("referred_columns", [])
            
            if not constrained_columns or not referred_table:
                continue
            
            fk_column = constrained_columns[0]
            parent_pk = referred_columns[0] if referred_columns else "id"
            
            print(f"  🔗 FK: {fk_column} -> {referred_table}.{parent_pk}")
            
            # Проверяем orphaned records
            orphan_count = check_orphaned_records(conn, table, fk_column, referred_table, parent_pk)
            
            if orphan_count > 0:
                results["orphaned_records"].append({
                    "table": table,
                    "column": fk_column,
                    "parent_table": referred_table,
                    "parent_pk": parent_pk,
                    "count": orphan_count
                })
                print(f"    ❌ Найдено {orphan_count} orphaned записей!")
            elif orphan_count == 0:
                print(f"    ✅ Нет orphaned записей")
            else:
                results["errors"].append({
                    "table": table,
                    "column": fk_column,
                    "error": "Check failed"
                })
        
        print()
    
    return results


def main():
    """Основная функция"""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Пробуем получить из настроек
        try:
            from app.core.config import settings
            url = getattr(settings, "DATABASE_URL", None)
        except Exception:
            pass
    
    if not url:
        url = "sqlite:///./clinic.db"
        print(f"⚠️  DATABASE_URL не установлен, используем: {url}", file=sys.stderr)
    
    # Нормализуем SQLite URL
    if url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    
    engine = sa.create_engine(url, future=True)
    
    with engine.connect() as conn:
        # ✅ SECURITY: Включаем проверку FK для SQLite
        if url.startswith("sqlite"):
            conn.execute(text("PRAGMA foreign_keys=ON"))
            print("✅ Foreign key enforcement включен для SQLite\n")
        
        # Проверяем, включены ли FK
        if url.startswith("sqlite"):
            fk_status = conn.execute(text("PRAGMA foreign_keys")).fetchone()
            if fk_status and fk_status[0]:
                print("✅ Foreign keys включены в SQLite\n")
            else:
                print("⚠️  WARNING: Foreign keys НЕ включены в SQLite!\n")
        
        # Выполняем аудит
        results = audit_all_foreign_keys(conn)
    
    # Выводим итоговый отчет
    print("=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    print(f"Всего таблиц: {results['total_tables']}")
    print(f"Таблиц с FK: {results['tables_with_fks']}")
    print(f"Всего FK: {results['total_fks']}")
    print(f"Orphaned записей найдено: {len(results['orphaned_records'])}")
    print(f"Ошибок: {len(results['errors'])}")
    print()
    
    if results['orphaned_records']:
        print("⚠️  ORPHANED RECORDS НАЙДЕНЫ:")
        for orphan in results['orphaned_records']:
            print(f"  - {orphan['table']}.{orphan['column']} -> {orphan['parent_table']}.{orphan['parent_pk']}: {orphan['count']} записей")
        print()
        print("Рекомендация: Исправьте orphaned записи перед включением FK enforcement.")
        return 1
    else:
        print("✅ Orphaned records не найдены. FK enforcement можно безопасно включить.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

