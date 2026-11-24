"""REG-XC-001 (follow-up audit 2026-11-02): персистентность JSON
``Visit.doctor_price_override`` при ВТОРОМ согласовании цены.

Дефект: колонка — обычный ``mapped_column(JSON)`` без ``MutableDict``;
прежний код мутировал словарь in-place. Первое согласование (None → ``{}``)
маркировало атрибут dirty и случайно сохранялось, но ВТОРОЕ согласование на
непустом словаре проходило без присваивания/``flag_modified`` — SQLAlchemy
не видел изменения, endpoint возвращал 2xx и ``status='approved'`` у
DoctorPriceOverride, а JSON визита в БД оставался прежним.

Red-first: визит с уже сохранённым override услуги A; второе согласование
услуги B; НОВАЯ сессия БД обязана видеть оба A и B. Мок-тест этого класса
не ловит (dirty-трекинг — свойство сессии), поэтому тест поднимает
собственный SQLite-движок и проверяет фикс честной перезагрузкой.
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import base  # noqa: F401 — регистрация всех моделей
from app.db.base_class import Base
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.price_override_approval import PriceOverrideApprovalService
from app.services.profile_contact_security import ProfileBearerContext
from tests.synthetic_reconciliation import install_reconciliation_fence


@pytest.fixture()
def fresh_engine():
    """Изолированный файловый SQLite: коммиты видны новой сессией."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    try:
        install_reconciliation_fence(engine)
        yield engine
    finally:
        engine.dispose()
        try:
            os.unlink(db_path)
        except OSError:
            pass


def _seed(engine, *, existing_mirror=True) -> tuple[int, int, int]:
    """Визит с УЖЕ сохранённым override услуги A + pending override B."""
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        user = User(
            username="reg_xc_approver",
            email="regxc@example.com",
            full_name="Registrar XC",
            hashed_password="not-a-real-hash",
            role="Admin",
            is_active=True,
        )
        patient = Patient(last_name="XC", first_name="Patient")
        service_b = Service(id=202, code="SYNTHETIC-B", name="Synthetic service B", price=Decimal("200000.00"))
        session.add_all([user, patient, service_b])
        session.flush()
        encounter = Encounter(patient_id=patient.id, provenance="new")
        session.add(encounter)
        session.flush()

        visit = Visit(
            patient_id=patient.id,
            encounter_id=encounter.id,
            status="open",
            confirmation_context_epoch=43,
            # Услуга A уже согласована ранее и ПЕРСИСТЕЙБЛЬНО хранится.
            doctor_price_override={
                "101": {
                    "original_price": 100000.0,
                    "new_price": 110000.0,
                    "override_id": 9001,
                    "approved_at": "2026-11-01T09:00:00+00:00",
                }
            } if existing_mirror else None,
        )
        session.add(visit)
        session.flush()

        # REGPRICE-BE-001 (audit 3892, group 16): the canonical approval
        # fail-closes when the chargeable VisitService row is missing — the
        # JSON-persistence contract under test needs the attached row.
        line_b = VisitService(
            visit_id=visit.id,
            service_id=service_b.id,
            code="202",
            name="XC service B",
            qty=1,
            price=Decimal("200000.00"),
            currency="UZS",
        )
        session.add(line_b)
        session.flush()

        override_b = DoctorPriceOverride(
            visit_id=visit.id,
            service_id=202,
            target_scope="visit_service",
            target_visit_service_id=line_b.id,
            visit_context_epoch=visit.confirmation_context_epoch,
            price_context_generation=visit.price_context_generation,
            price_line_generation=line_b.price_line_generation,
            requester_type="admin",
            requester_user_id=user.id,
            requester_user_id_snapshot=user.id,
            requester_auth_epoch=user.auth_epoch,
            original_price=Decimal("200000.00"),
            visit_price_before=line_b.price,
            new_price=Decimal("250000.00"),
            reason="REG-XC-001 second approval persistence",
            status="pending",
        )
        session.add(override_b)
        session.commit()

        return user.id, visit.id, override_b.id


def _approve(engine, actor_id, override_id) -> None:
    with sessionmaker(bind=engine)() as session:
        actor = session.get(User, actor_id)
        assert actor is not None
        result = PriceOverrideApprovalService(session).process(
            override_id=override_id,
            action="approve",
            rejection_reason=None,
            approver_id=actor_id,
            bearer=ProfileBearerContext(actor_id, actor.auth_epoch, None, None, None),
        )
        assert result.status == "approved"


def test_second_price_override_persists_visit_json(fresh_engine) -> None:
    user_id, visit_id, override_b_id = _seed(fresh_engine)
    _approve(fresh_engine, user_id, override_b_id)

    # НОВАЯ сессия: 2xx и approved у override — НЕ доказательство, что JSON
    # визита сохранён. Проверяем именно перечитыванием из БД.
    verify_session = sessionmaker(bind=fresh_engine)()
    try:
        persisted = verify_session.get(Visit, visit_id)
        assert persisted is not None
        stored = persisted.doctor_price_override or {}

        # Услуга A (первое согласование) не потеряна.
        assert stored.get("101", {}).get("new_price") == 110000.0
        # Услуга B (второе согласование) ДОБАВЛЕНА и видна новой сессии —
        # до фикса in-place мутация не попадала в UPDATE, B отсутствовал.
        assert "202" in stored, (
            "REG-XC-001 regression: second approval did not persist "
            f"into Visit.doctor_price_override (stored keys: {sorted(stored)})"
        )
        assert stored["202"]["new_price"] == 250000.0
        assert stored["202"]["original_price"] == 200000.0
        assert stored["202"]["override_id"] == override_b_id
        assert stored["202"]["approved_at"] is not None
    finally:
        verify_session.close()


def test_first_price_override_still_persists_from_empty_json(fresh_engine) -> None:
    user_id, visit_id, override_id = _seed(fresh_engine, existing_mirror=False)
    _approve(fresh_engine, user_id, override_id)
    with sessionmaker(bind=fresh_engine)() as session:
        stored = session.get(Visit, visit_id).doctor_price_override
        assert stored["202"]["new_price"] == 250000.0


def test_approved_at_is_set_on_override_row(fresh_engine) -> None:
    user_id, _, override_id = _seed(fresh_engine, existing_mirror=False)
    _approve(fresh_engine, user_id, override_id)
    with sessionmaker(bind=fresh_engine)() as session:
        row = session.get(DoctorPriceOverride, override_id)
        assert row.status == "approved"
        assert row.approved_by == user_id
        assert row.approved_at is not None
