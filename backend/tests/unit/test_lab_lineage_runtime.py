"""A+ runtime acceptance: managed lineage projection (owner contract).

Контракт: .ai-factory/plans/lab-results-lineage-decision.md (C → A+).
Каждый тест ссылается на строку приёмочной матрицы контракта. Уровень:
сервис (SQLite-харнес); сериализация/конкурентность на реальном PG
доказаны отдельными двухсоединечными тестами и пинами CI.
"""
from __future__ import annotations

from datetime import date, datetime, UTC
from decimal import Decimal
from uuid import uuid4

import pytest

from app.crud.lab_result import delete_lab_result, update_lab_result
from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.lab import LabResultUpdate
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)


def _mk_visit(db_session, tag: str):
    suffix = uuid4().hex[:8]
    patient = Patient(
        first_name="Lineage",
        last_name=f"{tag}{suffix}",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    visit = Visit(
        patient_id=patient.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return patient, visit


def _finalize_blank(db_session, patient_id: int, visit_id: int, template, values):
    service = LabReportingService(db_session)
    instance = service.create_instance(
        {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "template_id": template.id,
        }
    )
    if values:
        service.bulk_upsert_values(instance.id, values)
    finalized = service.finalize(instance.id)
    return service, finalized


def _glucose_rows(db_session, order_id: int) -> list[LabResult]:
    return (
        db_session.query(LabResult)
        .filter(LabResult.order_id == order_id, LabResult.test_code == "glucose")
        .order_by(LabResult.id)
        .all()
    )


def test_sibling_blanks_same_code_two_independent_chains(db_session):
    """Матрица: биохимия + ОАМ с одинаковым кодом, оба порядка → два
    независимых результата; EMR/mobile-эквивалент (list-read) видит обе."""
    _, visit = _mk_visit(db_session, "Sib")
    service = LabReportingService(db_session)
    templates = service.list_templates()
    biochem = next(t for t in templates if t.code == "biochem_panel")
    urinalysis = next(t for t in templates if t.code == "urinalysis_oam")

    _, blood = _finalize_blank(
        db_session, visit.patient_id, visit.id, biochem,
        [{"field_key": "glucose", "value_text": "5.4"}],
    )
    _, urine = _finalize_blank(
        db_session, visit.patient_id, visit.id, urinalysis,
        [{"field_key": "glucose", "value_text": "не обнаружено"}],
    )
    assert blood.order_id == urine.order_id

    rows = _glucose_rows(db_session, blood.order_id)
    assert len(rows) == 2, "both sibling results must coexist"
    assert {row.value for row in rows} == {"5.4", "не обнаружено"}
    assert len({row.source_root_instance_id for row in rows}) == 2, (
        "each sibling blank is its own lineage chain"
    )
    assert all(row.abnormal is False for row in rows)

    # Consumer-equivalent read (mobile/EMR read lists by test_code):
    listed = (
        db_session.query(LabResult)
        .filter(LabResult.test_code == "glucose")
        .join(LabOrder)
        .filter(LabOrder.patient_id == visit.patient_id)
        .all()
    )
    assert len(listed) == 2


def test_two_blanks_same_template_two_chains(db_session):
    """Матрица: два самостоятельных бланка одного шаблона → две цепочки."""
    _, visit = _mk_visit(db_session, "Same")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    _, first = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )
    _, second = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "120"}],
    )
    assert first.order_id == second.order_id

    rows = (
        db_session.query(LabResult)
        .filter(LabResult.order_id == first.order_id, LabResult.test_code == "hgb")
        .all()
    )
    assert len(rows) == 2
    assert {row.value for row in rows} == {"100", "120"}
    assert len({row.source_root_instance_id for row in rows}) == 2


def test_revision_chain_keeps_single_current_projection(db_session):
    """Матрица: A → A2 → A3: одна актуальная проекция цепочки; каноническая
    история сохранена в утверждённых instances; source движется по цепочке."""
    _, visit = _mk_visit(db_session, "Chain")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )

    hgb_rows = lambda: (  # noqa: E731
        db_session.query(LabResult)
        .filter(
            LabResult.source_root_instance_id == a.id,
            LabResult.test_code == "hgb",
        )
        .all()
    )

    a2 = service.revise(a.id)
    service.bulk_upsert_values(a2.id, [{"field_key": "hgb", "value_text": "140"}])
    service.finalize(a2.id)
    rows = hgb_rows()
    assert len(rows) == 1
    assert rows[0].value == "140"
    assert rows[0].source_instance_id == a2.id

    a3 = service.revise(a2.id)
    service.bulk_upsert_values(a3.id, [{"field_key": "hgb", "value_text": "150"}])
    service.finalize(a3.id)
    rows = hgb_rows()
    assert len(rows) == 1, "chain keeps ONE current projection"
    assert rows[0].value == "150"
    assert rows[0].source_instance_id == a3.id
    # Каноническая история — в неизменяемых утверждённых бланках:
    assert a.status == "FINALIZED" and a2.status == "FINALIZED"


def test_resync_of_superseded_version_is_refused(db_session):
    """Матрица: re-sync A после A3 — A3 не заменяется старым значением
    (контролируемый конфликт, актуальность задаёт цепочка)."""
    _, visit = _mk_visit(db_session, "Resync")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )
    a2 = service.revise(a.id)
    service.bulk_upsert_values(a2.id, [{"field_key": "hgb", "value_text": "140"}])
    service.finalize(a2.id)

    with pytest.raises(LabReportingDomainError) as exc:
        service._sync_legacy_lab_results(a, service._field_map(a.template_version))
    assert exc.value.status_code == 409

    row = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id, LabResult.test_code == "hgb")
        .one()
    )
    assert row.value == "140" and row.source_instance_id == a2.id


def test_competing_revision_gets_controlled_conflict(db_session):
    """Матрица: две конкурирующие ревизии одного предшественника — первая
    утверждённая становится текущей, вторая получает 409 без потери данных."""
    _, visit = _mk_visit(db_session, "Comp")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )
    first = service.revise(a.id)
    service.bulk_upsert_values(first.id, [{"field_key": "hgb", "value_text": "140"}])
    service.finalize(first.id)

    second = service.revise(a.id)  # sibling of `first`, supersedes A only
    service.bulk_upsert_values(second.id, [{"field_key": "hgb", "value_text": "999"}])
    with pytest.raises(LabReportingDomainError) as exc:
        service.finalize(second.id)
    assert exc.value.status_code == 409

    db_session.rollback()
    row = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id, LabResult.test_code == "hgb")
        .one()
    )
    assert row.value == "140" and row.source_instance_id == first.id, (
        "the first finalized revision stays current; no silent overwrite"
    )


def test_finalize_is_atomic_when_projection_fails(db_session, monkeypatch):
    """Матрица: ошибка записи проекции — финализация не коммитится
    частично (статус и проекция откатываются вместе)."""
    _, visit = _mk_visit(db_session, "Atom")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")
    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )

    a2 = service.revise(a.id)
    service.bulk_upsert_values(a2.id, [{"field_key": "hgb", "value_text": "140"}])
    # Инъекция: коммит окружающего finalize падает на этапе проекции —
    # транзакция (статус FINALIZED + разрешённые флаги + записи проекции)
    # обязана откатиться целиком.
    def _boom_commit():
        raise RuntimeError("injected projection failure")

    finalizing = LabReportingService(db_session)
    monkeypatch.setattr(finalizing.repository, "commit", _boom_commit)
    with pytest.raises(RuntimeError):
        finalizing.finalize(a2.id)
    db_session.rollback()

    refreshed = service.get_instance(a2.id)
    assert refreshed.status != "FINALIZED", "no partial commit"
    rows = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id)
        .all()
    )
    assert len(rows) == 1 and rows[0].value == "100", (
        "the failed revision must not touch the current projection"
    )


def test_cleared_indicator_stops_being_current(db_session):
    """Матрица: очищение показателя — прежнее значение больше не актуально;
    пустота не превращается в старое значение или «норму»."""
    _, visit = _mk_visit(db_session, "Clear")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )
    a2 = service.revise(a.id)
    service.bulk_upsert_values(a2.id, [{"field_key": "hgb", "value_text": ""}])
    service.finalize(a2.id)

    row = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id, LabResult.test_code == "hgb")
        .one()
    )
    assert row.value is None, "no stale current value after clearing"
    assert row.abnormal is False
    assert row.source_instance_id == a2.id, "source points at the clearing revision"


def test_historical_rows_untouched_by_new_chains(db_session):
    """Матрица: исторические строки без source — не привязаны к цепочкам
    и не перезаписываются новыми бланками того же заказа."""
    _, visit = _mk_visit(db_session, "Hist")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    instance = service.create_instance(
        {"patient_id": visit.patient_id, "visit_id": visit.id, "template_id": cbc.id}
    )
    order_id = instance.order_id
    historical = LabResult(
        order_id=order_id,
        test_code="hgb",
        test_name="Historical hgb",
        value="90",
        abnormal=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(historical)
    db_session.commit()
    db_session.refresh(historical)

    service.bulk_upsert_values(
        instance.id, [{"field_key": "hgb", "value_text": "100"}]
    )
    service.finalize(instance.id)

    db_session.refresh(historical)
    assert historical.value == "90"
    assert historical.source_root_instance_id is None
    assert historical.id == historical.id  # identity preserved

    managed = (
        db_session.query(LabResult)
        .filter(
            LabResult.order_id == order_id,
            LabResult.source_root_instance_id.isnot(None),
        )
        .all()
    )
    assert len(managed) == 1 and managed[0].value == "100"


def test_legacy_writers_cannot_mutate_managed_rows(db_session):
    """Матрица: legacy update/delete управляемой строки — обход канонического
    writer запрещён; строки без lineage пишутся как раньше."""
    _, visit = _mk_visit(db_session, "Guard")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")

    instance = service.create_instance(
        {"patient_id": visit.patient_id, "visit_id": visit.id, "template_id": cbc.id}
    )
    service.bulk_upsert_values(
        instance.id, [{"field_key": "hgb", "value_text": "100"}]
    )
    service.finalize(instance.id)
    managed = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id.isnot(None))
        .one()
    )

    with pytest.raises(ValueError):
        update_lab_result(
            db_session, managed.id, LabResultUpdate(value="tampered")
        )
    with pytest.raises(ValueError):
        delete_lab_result(db_session, managed.id)

    legacy = LabResult(
        order_id=instance.order_id,
        test_code="manual_entry",
        test_name="Manual legacy entry",
        value="1",
        abnormal=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)
    updated = update_lab_result(
        db_session, legacy.id, LabResultUpdate(value="2")
    )
    assert updated is not None and updated.value == "2"
    assert delete_lab_result(db_session, legacy.id) is True


def test_idempotent_resync_does_not_replay_notifications(db_session):
    """Контракт (уведомления): повторный sync того же утверждённого бланка —
    нет новых строк и нет обновления created_at (critical-value сканер
    читает created_at; re-sync не порождает повторных событий)."""
    _, visit = _mk_visit(db_session, "Idem")
    service = LabReportingService(db_session)
    cbc = next(t for t in service.list_templates() if t.code == "cbc_oak")
    _, a = _finalize_blank(
        db_session, visit.patient_id, visit.id, cbc,
        [{"field_key": "hgb", "value_text": "100"}],
    )
    before = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id)
        .all()
    )
    created_before = [row.created_at for row in before]

    service._sync_legacy_lab_results(a, service._field_map(a.template_version))
    db_session.commit()

    after = (
        db_session.query(LabResult)
        .filter(LabResult.source_root_instance_id == a.id)
        .all()
    )
    assert len(after) == len(before)
    assert [row.created_at for row in after] == created_before


def test_sibling_blanks_reverse_finalize_order(db_session):
    """Матрица («оба порядка»): ОАМ финализируется первым — обратный
    порядок не меняет исход: два независимых результата сосуществуют."""
    _, visit = _mk_visit(db_session, "Rev")
    service = LabReportingService(db_session)
    templates = service.list_templates()
    biochem = next(t for t in templates if t.code == "biochem_panel")
    urinalysis = next(t for t in templates if t.code == "urinalysis_oam")

    _, urine = _finalize_blank(
        db_session, visit.patient_id, visit.id, urinalysis,
        [{"field_key": "glucose", "value_text": "не обнаружено"}],
    )
    _, blood = _finalize_blank(
        db_session, visit.patient_id, visit.id, biochem,
        [{"field_key": "glucose", "value_text": "5.4"}],
    )
    rows = _glucose_rows(db_session, blood.order_id)
    assert len(rows) == 2
    assert {row.value for row in rows} == {"5.4", "не обнаружено"}
    assert len({row.source_root_instance_id for row in rows}) == 2
