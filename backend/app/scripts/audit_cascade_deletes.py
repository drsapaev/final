#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аудит cascade delete стратегий в моделях

✅ SECURITY: Проверяет все FK связи и их cascade поведение
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

import sqlalchemy as sa
from sqlalchemy import inspect

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def audit_cascade_strategies(conn) -> Dict[str, List[Dict]]:
    """Аудит всех cascade стратегий в базе данных"""
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    results = {
        "missing_cascade": [],
        "inconsistent_cascade": [],
        "orphan_risk": [],
        "safe_cascade": [],
    }
    
    print("=" * 80)
    print("АУДИТ CASCADE DELETE СТРАТЕГИЙ")
    print("=" * 80)
    print()
    
    # Критические связи, которые должны иметь cascade
    critical_relationships = {
        # User -> related entities (should cascade)
        ("users", "refresh_tokens", "user_id"): "CASCADE",
        ("users", "user_sessions", "user_id"): "CASCADE",
        ("users", "password_reset_tokens", "user_id"): "CASCADE",
        ("users", "email_verification_tokens", "user_id"): "CASCADE",
        ("users", "login_attempts", "user_id"): "CASCADE",
        ("users", "user_activities", "user_id"): "CASCADE",
        ("users", "security_events", "user_id"): "CASCADE",
        
        # Visit -> related entities
        ("visits", "visit_services", "visit_id"): "CASCADE",
        ("visits", "prescriptions", "visit_id"): "CASCADE",
        ("visits", "emr", "visit_id"): "SET NULL",  # EMR should be preserved
        
        # Payment -> related entities
        ("payments", "payment_transactions", "payment_id"): "CASCADE",
        ("payments", "payment_webhooks", "payment_id"): "SET NULL",  # Webhooks should be preserved for audit
        
        # Department -> related entities
        ("departments", "department_services", "department_id"): "CASCADE",
        ("departments", "department_queue_settings", "department_id"): "CASCADE",
        ("departments", "department_registration_settings", "department_id"): "CASCADE",
        
        # File -> related entities
        ("files", "file_versions", "file_id"): "CASCADE",
        ("files", "file_shares", "file_id"): "CASCADE",
        
        # Online Queue -> related entities
        ("daily_queues", "online_queue_entries", "queue_id"): "CASCADE",
    }
    
    # Связи, которые НЕ должны иметь cascade (для сохранения данных)
    preserve_relationships = {
        ("patients", "visits", "patient_id"): "SET NULL",  # Visits should be preserved
        ("patients", "appointments", "patient_id"): "SET NULL",  # Appointments should be preserved
        ("users", "visits", "doctor_id"): "SET NULL",  # Visits should be preserved
        ("users", "appointments", "doctor_id"): "SET NULL",  # Appointments should be preserved
    }
    
    for table in tables:
        try:
            fks = inspector.get_foreign_keys(table)
            
            for fk in fks:
                constrained_table = table
                constrained_columns = fk.get("constrained_columns", [])
                referred_table = fk.get("referred_table", "")
                referred_columns = fk.get("referred_columns", [])
                fk_name = fk.get("name", "unnamed")
                
                if not constrained_columns or not referred_table:
                    continue
                
                constrained_col = constrained_columns[0]
                key = (referred_table, constrained_table, constrained_col)
                
                # Проверяем ondelete
                ondelete = fk.get("options", {}).get("ondelete")
                
                # Проверяем критичность связи
                expected_cascade = critical_relationships.get(key)
                should_preserve = preserve_relationships.get(key)
                
                if expected_cascade:
                    if ondelete != expected_cascade:
                        results["inconsistent_cascade"].append({
                            "table": constrained_table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "current": ondelete or "NONE",
                            "expected": expected_cascade,
                            "fk_name": fk_name,
                        })
                        print(f"[WARNING] {constrained_table}.{constrained_col} -> {referred_table}")
                        print(f"     Текущий: {ondelete or 'NONE'}, Ожидается: {expected_cascade}")
                    else:
                        results["safe_cascade"].append({
                            "table": constrained_table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "cascade": ondelete,
                        })
                        print(f"[OK] {constrained_table}.{constrained_col} -> {referred_table}: {ondelete}")
                
                elif should_preserve:
                    if ondelete and ondelete != "SET NULL":
                        results["orphan_risk"].append({
                            "table": constrained_table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "current": ondelete,
                            "recommended": "SET NULL",
                            "reason": "Data should be preserved",
                        })
                        print(f"[WARNING] {constrained_table}.{constrained_col} -> {referred_table}")
                        print(f"     Текущий: {ondelete}, Рекомендуется: SET NULL (данные должны сохраняться)")
                
                # Проверяем отсутствие cascade для важных связей
                elif not ondelete and referred_table in ["users", "patients", "visits", "payments"]:
                    results["missing_cascade"].append({
                        "table": constrained_table,
                        "column": constrained_col,
                        "parent_table": referred_table,
                        "fk_name": fk_name,
                    })
                    print(f"[ERROR] {constrained_table}.{constrained_col} -> {referred_table}: НЕТ CASCADE")
        
        except Exception as e:
                        print(f"[WARNING] Ошибка проверки таблицы {table}: {e}")
    
    return results


def main():
    """Основная функция"""
    url = os.getenv("DATABASE_URL")
    if not url:
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
        results = audit_cascade_strategies(conn)
    
    # Выводим итоговый отчет
    print()
    print("=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    print(f"[OK] Правильные cascade: {len(results['safe_cascade'])}")
    print(f"[WARNING] Несоответствия: {len(results['inconsistent_cascade'])}")
    print(f"[ERROR] Отсутствующие cascade: {len(results['missing_cascade'])}")
    print(f"[WARNING] Риск потери данных: {len(results['orphan_risk'])}")
    print()
    
    if results["inconsistent_cascade"] or results["missing_cascade"]:
        print("[WARNING] ОБНАРУЖЕНЫ ПРОБЛЕМЫ С CASCADE DELETE!")
        return 1
    else:
        print("[OK] Все cascade стратегии корректны")
        return 0


if __name__ == "__main__":
    sys.exit(main())

