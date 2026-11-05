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
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints.registrar_wizard._cart import (
    approve_price_override,
    PriceOverrideApprovalRequest,
)
from app.db import base  # noqa: F401 — регистрация всех моделей
from app.db.base_class import Base
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


@pytest.fixture()
def fresh_engine():
    """Изолированный файловый SQLite: коммиты видны новой сессией."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()
        try:
            os.unlink(db_path)
        except OSError:
            pass


def _seed(engine) -> tuple[int, int, int]:
    """Визит с УЖЕ сохранённым override услуги A + pending override B."""
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        user = User(
            username="reg_xc_approver",
            email="regxc@example.com",
            full_name="Registrar XC",
            hashed_password="not-a-real-hash",
            role="Registrar",
            is_active=True,
        )
        patient = Patient(last_name="XC", first_name="Patient")
        session.add(user)
        session.add(patient)
        session.flush()

        visit = Visit(
            patient_id=patient.id,
            status="open",
            # Услуга A уже согласована ранее и ПЕРСИСТЕЙБЛЬНО хранится.
            doctor_price_override={
                "101": {
                    "original_price": 100000.0,
                    "new_price": 110000.0,
                    "override_id": 9001,
                    "approved_at": "2026-11-01T09:00:00+00:00",
                }
            },
        )
        session.add(visit)
        session.flush()

        override_b = DoctorPriceOverride(
            visit_id=visit.id,
            service_id=202,
            original_price=Decimal("200000.00"),
            new_price=Decimal("250000.00"),
            reason="REG-XC-001 second approval persistence",
            status="pending",
        )
        session.add(override_b)
        session.commit()

        return user.id, visit.id, override_b.id


def test_second_price_override_persists_visit_json(fresh_engine) -> None:
    user_id, visit_id, override_b_id = _seed(fresh_engine)

    approve_session = sessionmaker(bind=fresh_engine)()
    try:
        approver = approve_session.get(User, user_id)
        result = approve_price_override(
            PriceOverrideApprovalRequest(override_id=override_b_id, action="approve"),
            db=approve_session,
            current_user=approver,
        )
        assert result["success"] is True
        assert result["new_status"] == "approved"
    finally:
        approve_session.close()

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
    """Регресс-обёртка прежнего рабочего пути: первое согласование (JSON
    пуст) обязано сохраняться и после перехода на присваивание нового
    словаря."""
    SessionLocal = sessionmaker(bind=fresh_engine)
    with SessionLocal() as session:
        user = User(
            username="reg_xc_first",
            email="regxc1@example.com",
            full_name="Registrar XC1",
            hashed_password="not-a-real-hash",
            role="Registrar",
            is_active=True,
        )
        patient = Patient(last_name="XC", first_name="First")
        session.add(user)
        session.add(patient)
        session.flush()
        visit = Visit(patient_id=patient.id, status="open", doctor_price_override=None)
        session.add(visit)
        session.flush()
        override = DoctorPriceOverride(
            visit_id=visit.id,
            service_id=303,
            original_price=Decimal("50000.00"),
            new_price=Decimal("60000.00"),
            reason="REG-XC-001 first approval regression",
            status="pending",
        )
        session.add(override)
        session.commit()
        user_id, visit_id, override_id = user.id, visit.id, override.id

    approve_session = SessionLocal()
    try:
        result = approve_price_override(
            PriceOverrideApprovalRequest(override_id=override_id, action="approve"),
            db=approve_session,
            current_user=approve_session.get(User, user_id),
        )
        assert result["success"] is True
    finally:
        approve_session.close()

    verify_session = SessionLocal()
    try:
        stored = verify_session.get(Visit, visit_id).doctor_price_override or {}
        assert stored.get("303", {}).get("new_price") == 60000.0
    finally:
        verify_session.close()


def test_approved_at_is_set_on_override_row(fresh_engine) -> None:
    """Побочная проверка контракта: строка override получает approved_*."""
    SessionLocal = sessionmaker(bind=fresh_engine)
    with SessionLocal() as session:
        user = User(
            username="reg_xc_ts",
            email="regxc2@example.com",
            full_name="Registrar XC2",
            hashed_password="not-a-real-hash",
            role="Registrar",
            is_active=True,
        )
        patient = Patient(last_name="XC", first_name="Ts")
        session.add(user)
        session.add(patient)
        session.flush()
        visit = Visit(patient_id=patient.id, status="open")
        session.add(visit)
        session.flush()
        override = DoctorPriceOverride(
            visit_id=visit.id,
            service_id=404,
            original_price=Decimal("10000.00"),
            new_price=Decimal("12000.00"),
            reason="REG-XC-001 approved_at contract",
            status="pending",
        )
        session.add(override)
        session.commit()
        user_id, override_id = user.id, override.id

    approve_session = SessionLocal()
    try:
        approve_price_override(
            PriceOverrideApprovalRequest(override_id=override_id, action="approve"),
            db=approve_session,
            current_user=approve_session.get(User, user_id),
        )
    finally:
        approve_session.close()

    verify_session = SessionLocal()
    try:
        row = verify_session.get(DoctorPriceOverride, override_id)
        assert row.status == "approved"
        assert row.approved_by == user_id
        # SQLite хранит naive-datetime: проверяем наличие, без сравнения
        # offset-aware «сейчас» (TypeErrors на naive vs aware).
        assert row.approved_at is not None
    finally:
        verify_session.close()
