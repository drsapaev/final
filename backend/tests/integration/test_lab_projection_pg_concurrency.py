"""A+ runtime regression: two-connection PostgreSQL concurrency proof.

Две параллельные финализации сиблинговых бланков одного заказа (разные
цепочки lineage) обязаны создать ДВЕ независимые управляемые проекции —
по одной на цепочку (managed-ключ source_root_instance_id + test_code
делает дубликат внутри цепочки невозможным на уровне схемы) — и обе
финализации завершаются. Сериализация цепочек: SELECT … FOR UPDATE на
root-instance в _sync_legacy_lab_results.

Требует реального PostgreSQL: SQLite игнорирует FOR UPDATE и глобально
сериализует запись, поэтому на SQLite этот тест ничего не доказывает.
Запуск: задайте LAB_PG_ADMIN_DSN (предпочтительно) или DATABASE_URL
(postgresql*), указывающие на сервер, где разрешено CREATE DATABASE;
тест создаёт одноразовую scratch-базу и удаляет её после прогона.
"""
from __future__ import annotations

import os
import threading
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.patient import Patient
from app.models.visit import Visit


def _admin_dsn() -> str | None:
    dsn = os.getenv("LAB_PG_ADMIN_DSN") or os.getenv("DATABASE_URL")
    if not dsn or not dsn.startswith("postgres"):
        return None
    return dsn


def _dbname_of(dsn: str) -> str:
    rest = dsn.split("://", 1)[1]
    hostpart, dbname = rest.rsplit("/", 1)
    if "?" in dbname:
        dbname = dbname.split("?", 1)[0]
    return dbname or "postgres"


def _server_dsn(dsn: str) -> str:
    rest = dsn.split("://", 1)[1]
    auth, hostpart = rest.rsplit("@", 1)
    host_only = hostpart.split("/", 1)[0]
    return f"postgresql+psycopg://{auth}@{host_only}/postgres"


@pytest.mark.integration
def test_concurrent_sibling_finalize_creates_independent_chain_projections():
    admin_dsn = _admin_dsn()
    if not admin_dsn:
        pytest.skip(
            "requires LAB_PG_ADMIN_DSN or DATABASE_URL pointing at a "
            "disposable PostgreSQL server (SQLite cannot prove FOR UPDATE "
            "semantics)"
        )

    scratch_name = f"lab_cguard_{uuid4().hex[:10]}"
    admin_engine = create_engine(_server_dsn(admin_dsn), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{scratch_name}"'))
    except Exception as exc:  # noqa: BLE001 - нет прав CREATE DATABASE и т.п.
        admin_engine.dispose()
        pytest.skip(
            f"cannot create a scratch database on this PostgreSQL server "
            f"({type(exc).__name__}); run against a server with CREATEDB"
        )

    scratch_dsn = _server_dsn(admin_dsn).rsplit("/", 1)[0] + f"/{scratch_name}"
    scratch_engine = create_engine(scratch_dsn)
    Base.metadata.create_all(bind=scratch_engine)
    ScratchSession = sessionmaker(bind=scratch_engine)

    order_id: int | None = None
    instance_ids: list[int] = []
    try:
        # Подготовка (однопоточно): два самостоятельных бланка одного заказа
        # с одинаковым field_key glucose — штатная seed-коллизия
        # biochem_panel (кровь) vs urinalysis_oam (моча).
        with ScratchSession() as session:
            suffix = uuid4().hex[:10]
            patient = Patient(
                first_name="Concurrency",
                last_name=f"Probe{suffix}",
                phone=f"+99890{suffix[:7]}",
                birth_date=date(1990, 1, 1),
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)

            visit = Visit(
                patient_id=patient.id,
                visit_date=date.today(),
                status="open",
                source="desk",
            )
            session.add(visit)
            session.commit()
            session.refresh(visit)

            from app.services.lab_reporting_service import LabReportingService

            service = LabReportingService(session)
            templates = service.list_templates()
            biochem = next(t for t in templates if t.code == "biochem_panel")
            urinalysis = next(t for t in templates if t.code == "urinalysis_oam")

            instance_a = service.create_instance(
                {
                    "patient_id": patient.id,
                    "visit_id": visit.id,
                    "template_id": biochem.id,
                }
            )
            service.bulk_upsert_values(
                instance_a.id,
                [{"field_key": "glucose", "value_text": "5.4"}],
            )
            instance_b = service.create_instance(
                {
                    "patient_id": patient.id,
                    "visit_id": visit.id,
                    "template_id": urinalysis.id,
                }
            )
            service.bulk_upsert_values(
                instance_b.id,
                [{"field_key": "glucose", "value_text": "не обнаружено"}],
            )
            assert instance_a.order_id is not None
            assert instance_a.order_id == instance_b.order_id, (
                "sibling blanks of one visit must share the order"
            )
            order_id = instance_a.order_id
            instance_ids = [instance_a.id, instance_b.id]

        # Гонка: две независимые сессии (== соединения) финализируют
        # одновременно; барьер выравнивает старт.
        barrier = threading.Barrier(2, timeout=60)
        errors: list[BaseException] = []

        def _finalize(instance_id: int) -> None:
            try:
                barrier.wait()
                with ScratchSession() as session:
                    from app.services.lab_reporting_service import (
                        LabReportingService,
                    )

                    LabReportingService(session).finalize(instance_id)
            except BaseException as exc:  # noqa: BLE001 - собираем для ассертов
                errors.append(exc)

        threads = [
            threading.Thread(target=_finalize, args=(iid,), name=f"finalize-{iid}")
            for iid in instance_ids
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=180)
        assert not any(thread.is_alive() for thread in threads), (
            "finalize threads deadlocked"
        )
        assert errors == [], f"finalize raised: {errors!r}"

        with ScratchSession() as session:
            rows = session.execute(
                text(
                    "SELECT source_root_instance_id, COUNT(*) AS n "
                    "FROM lab_results "
                    "WHERE order_id = :oid AND test_code = 'glucose' "
                    "GROUP BY source_root_instance_id"
                ),
                {"oid": order_id},
            ).fetchall()
            assert len(rows) == 2, (
                "A+: concurrent sibling finalizes must produce TWO "
                f"independent chain projections, got {rows!r}"
            )
            assert all(row.n == 1 for row in rows), (
                "each chain keeps exactly one current glucose projection"
            )
            statuses = session.execute(
                text(
                    "SELECT status, COUNT(*) FROM lab_report_instances "
                    "WHERE id = ANY(:ids) GROUP BY status"
                ),
                {"ids": instance_ids},
            ).fetchall()
            assert all(row[0] == "FINALIZED" for row in statuses), (
                f"both finalizes must succeed: {statuses!r}"
            )
    finally:
        scratch_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}" WITH (FORCE)'))
        admin_engine.dispose()
