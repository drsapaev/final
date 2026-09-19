#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P-01 backfill: создаёт LabResult projection для исторических FINALIZED/PRINTED
instances, которые были финализированы ДО bridge (PR #1672).

Bridge создаёт LabResult только при новых finalize() вызовах. Этот скрипт
обрабатывает instances, финализированные до bridge — они не имеют LabResult
projection, и mobile app / EMR / statistics их не видят.

Запуск (из backend/):
    DATABASE_URL=postgresql://user:pass@host:5432/dbname \
        python backfill_lab_results.py

    # Dry-run (показать что будет сделано, без изменений):
    DATABASE_URL=... python backfill_lab_results.py --dry-run

Безопасность:
    - --dry-run по умолчанию (явный --apply для реального выполнения)
    - Идемпотентный: пропускает instances у которых уже есть LabResult
    - Логирование каждого instance
    - Transaction per instance (atomic, isolated)

C-контракт (решение владельца, см.
.ai-factory/plans/lab-results-lineage-decision.md):
    - Проекция создаётся ТОЛЬКО для заказа без единой строки LabResult И
      с единственным финализированным бланком.
    - Заказы с несколькими FINALIZED/PRINTED instances
      (ambiguous_shared_order) НЕ обрабатываются автоматически: их
      происхождение недоказуемо, требуется read-only census и решение
      владельца.
    - Значения ревизий и сиблинговых бланков НЕ попадают в legacy до
      трека A+ — это утверждённое временное ограничение, поэтому фраза
      про "mobile app видит все исторические отчёты" после #3235/C неверна.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Поддержка запуска из backend/ или из корня
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError as exc:
    print(f"ERROR: SQLAlchemy не установлен: {exc}")
    print("Запустите из виртуального окружения backend:")
    print("  cd backend && source venv/bin/activate")
    sys.exit(2)


def get_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            from app.core.config import settings
            url = (
                getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
                or getattr(settings, "DATABASE_URL", None)
            )
        except Exception:
            pass
    if not url:
        print("ERROR: DATABASE_URL не задан.")
        sys.exit(1)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill LabResult projection для исторических FINALIZED instances"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Реально применить изменения (по умолчанию dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Только показать что будет сделано (по умолчанию)",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    url = get_db_url()
    print(f"─" * 70)
    print(f"Backfill LabResult projection")
    print(f"DB: {url.split('@')[-1] if '@' in url else url}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print(f"─" * 70)

    engine = create_engine(url)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        # 1. Найти все FINALIZED/PRINTED instances без LabResult projection
        instances = db.execute(text("""
            SELECT
                ri.id AS instance_id,
                ri.order_id,
                ri.patient_id,
                ri.status,
                ri.finalized_at,
                ri.template_version_id,
                (SELECT COUNT(*) FROM lab_results lr WHERE lr.order_id = ri.order_id)
                    AS existing_lab_results_count
            FROM lab_report_instances ri
            WHERE ri.status IN ('FINALIZED', 'PRINTED')
            ORDER BY ri.id ASC
        """)).fetchall()

        print(f"\nВсего FINALIZED/PRINTED instances: {len(instances)}")

        if not instances:
            print("Нечего backfill'ить.")
            return 0

        # 2. Классификация по заказам (C-контракт, см.
        # .ai-factory/plans/lab-results-lineage-decision.md)
        orders_finalized: dict = {}
        for r in instances:
            if r.order_id is not None:
                orders_finalized[r.order_id] = orders_finalized.get(r.order_id, 0) + 1
        shared_orders = {oid for oid, n in orders_finalized.items() if n > 1}

        needing_backfill = [r for r in instances if r.existing_lab_results_count == 0]
        already_has = [r for r in instances if r.existing_lab_results_count > 0]
        ambiguous = [r for r in needing_backfill if r.order_id in shared_orders]
        eligible = [r for r in needing_backfill if r.order_id not in shared_orders]

        print(f"  Уже имеют LabResult projection: {len(already_has)}")
        print(f"  Нуждаются в backfill:           {len(needing_backfill)}")
        print(f"    из них eligible (одиночный бланк заказа): {len(eligible)}")
        print(f"    из них ambiguous_shared_order:            {len(ambiguous)}")

        if ambiguous:
            print(
                "\n[!] ambiguous_shared_order — заказы с несколькими "
                "финализированными бланками (авто-выбор запрещён C-контрактом):"
            )
            by_order: dict = {}
            for r in ambiguous:
                by_order.setdefault(r.order_id, []).append(r)
            for oid in sorted(by_order):
                ids = ", ".join(f"#{r.instance_id}" for r in by_order[oid])
                print(f"    order #{oid}: instances {ids}")

        if not needing_backfill:
            print("\n[OK] Все instances уже имеют LabResult projection. Backfill не нужен.")
            return 0

        # 3. Показать детали для dry-run
        if dry_run:
            print(f"\n{'─' * 70}")
            print("DRY RUN — будут созданы LabResult projection только для eligible:")
            print(f"{'─' * 70}")
            print(f"  {'Instance #':<12}  {'Order #':<10}  {'Patient #':<12}  {'Status':<12}  {'Finalized':<20}")
            print(f"  {'-'*12}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*20}")
            for r in eligible[:20]:
                finalized = str(r.finalized_at)[:19] if r.finalized_at else "—"
                print(f"  {r.instance_id:<12}  {r.order_id or '—':<10}  {r.patient_id:<12}  {r.status:<12}  {finalized:<20}")
            if len(eligible) > 20:
                print(f"  ... и ещё {len(eligible) - 20}")
            print("\nДля применения запустите с --apply:")
            print("  DATABASE_URL=... python backfill_lab_results.py --apply")
            return 0

        # 4. APPLY: обрабатываем ТОЛЬКО eligible; ambiguous не трогаем
        print(f"\n{'─' * 70}")
        print(
            f"Применение backfill для {len(eligible)} eligible instances "
            f"(ambiguous_shared_order пропущены: {len(ambiguous)})..."
        )
        print(f"{'─' * 70}")

        try:
            from app.services.lab_reporting_service import LabReportingService
        except ImportError as exc:
            print(f"ERROR: Не удалось импортировать LabReportingService: {exc}")
            print("Запустите из директории backend/ с настроенным окружением")
            return 1

        service = LabReportingService(db)
        projected_count = 0
        skipped_existing_count = 0
        error_count = 0

        def _rows_for(order_id):
            return db.execute(text(
                "SELECT COUNT(*) FROM lab_results WHERE order_id = :order_id"
            ), {"order_id": order_id}).scalar()

        for r in eligible:
            instance_id = r.instance_id
            try:
                instance = service.get_instance(instance_id)
                if not instance.order_id:
                    print(f"  [!] Instance #{instance_id}: нет order_id, skip")
                    skipped_existing_count += 1
                    continue

                rows_before = _rows_for(instance.order_id)
                field_map = service._field_map(instance.template_version)
                service._sync_legacy_lab_results(instance, field_map)
                db.commit()
                rows_after = _rows_for(instance.order_id)
                created = rows_after - rows_before

                if created > 0:
                    print(f"  [OK] Instance #{instance_id}: создано {created} LabResult projection")
                    projected_count += 1
                else:
                    # C-guard пропустил заказ (строки уже есть) — это НЕ успех.
                    print(
                        f"  [--] Instance #{instance_id}: projection пропущена "
                        f"C-guard'ом (у заказа уже есть строки) [skipped_existing]"
                    )
                    skipped_existing_count += 1
            except Exception as exc:
                db.rollback()
                print(f"  [X] Instance #{instance_id}: {exc}")
                error_count += 1

        print(f"\n{'=' * 70}")
        print("BACKFILL ЗАВЕРШЁН")
        print(f"{'=' * 70}")
        print(f"  projected:              {projected_count}")
        print(f"  skipped_existing:       {skipped_existing_count}")
        print(f"  ambiguous_shared_order: {len(ambiguous)} (не обрабатывались)")
        print(f"  failed:                 {error_count}")
        print(f"  Всего FINALIZED/PRINTED: {len(instances)}")

        if error_count > 0:
            print(f"\n[!] {error_count} instances с ошибками — проверьте логи выше.")
            return 1

        print(
            "\n[i] C-контракт (.ai-factory/plans/lab-results-lineage-decision.md): "
            "создание проекции ограничено заказами без строк и с единственным "
            "финализированным бланком. Значения ревизий и сиблинговых бланков НЕ "
            "видны в legacy до трека A+; ambiguous заказы требуют read-only census "
            "и решения владельца. Backfill НЕ восстанавливает полноту исторической "
            "проекции."
        )
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
