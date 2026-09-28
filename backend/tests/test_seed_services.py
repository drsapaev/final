"""Idempotency and insert-only guarantees for app.scripts.seed_services."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.clinic import ServiceCategory
from app.models.service import Service
from app.scripts.seed_services import CATEGORIES, SERVICES, seed_services_catalog


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed_services.db'}")
    ServiceCategory.__table__.create(engine)
    Service.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def _counts(db):
    return (
        db.query(ServiceCategory).count(),
        db.query(Service).count(),
    )


def test_seed_inserts_full_catalog(db):
    summary = seed_services_catalog(db)
    assert summary == {
        "categories_inserted": len(CATEGORIES),
        "categories_existing": 0,
        "services_inserted": len(SERVICES),
        "services_existing": 0,
    }
    assert _counts(db) == (len(CATEGORIES), len(SERVICES))


def test_seed_is_idempotent(db):
    seed_services_catalog(db)
    summary = seed_services_catalog(db)
    assert summary["categories_inserted"] == 0
    assert summary["services_inserted"] == 0
    assert _counts(db) == (len(CATEGORIES), len(SERVICES))


def test_seed_does_not_clobber_existing_rows(db):
    seed_services_catalog(db)
    k01 = db.query(Service).filter(Service.code == "K01").first()
    k01.name = "Консультация кардиолога (акция)"
    k01.price = 1000
    db.commit()

    seed_services_catalog(db)

    k01 = db.query(Service).filter(Service.code == "K01").first()
    assert k01.name == "Консультация кардиолога (акция)"
    assert float(k01.price) == 1000


def test_seed_resolves_category_links_by_code(db):
    seed_services_catalog(db)
    k01 = db.query(Service).filter(Service.code == "K01").first()
    cat = (
        db.query(ServiceCategory)
        .filter(ServiceCategory.code == "consultation.cardiology")
        .first()
    )
    assert k01.category_id == cat.id


def test_long_service_codes_stay_null(db):
    seed_services_catalog(db)
    for code in ("LAB_BILE_URINE", "LAB_GLUCOSE_FAST"):
        service = db.query(Service).filter(Service.code == code).one()
        assert service.service_code is None
        assert service.code == code


def test_doctor_performed_services_carry_specialty_department_key(db):
    """Workstream A (registrar doctor-services plan, Task 2).

    Врач-исполняемые услуги каталога несут department_key: без него
    accepted_specialties = None и услуга предлагается КАЖДОЙ карточке
    врача («нет specialty mapping» = конфиг-ошибка, не «все врачи»).
    Пин покрывает консультации K01/D01/S01, кардио-диагностику K11 и
    стоматологическую рентгенографию S10.
    """
    seed_services_catalog(db)
    expected = {
        "K01": "cardiology",
        "K11": "cardiology",
        "D01": "dermatology",
        "S01": "stomatology",
        "S10": "stomatology",
    }
    for code, key in expected.items():
        service = db.query(Service).filter(Service.code == code).one()
        assert service.requires_doctor is True, code
        assert service.department_key == key, code
