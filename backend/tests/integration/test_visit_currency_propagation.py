"""Only a trusted catalog snapshot may assign currency to new visit lines."""
import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.visit import create_visit
from app.db.base_class import Base
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.qr_queue._visits import VisitsMixin


class _Qr(VisitsMixin):
    def __init__(self, db):
        self.db = db


@pytest.fixture
def catalog(db_session):
    patient = Patient(first_name="SYNTHETIC", last_name="Currency")
    service = Service(code="SYNTHETIC-CURRENCY", name="SYNTHETIC", price=Decimal("0.07"),
                      currency="UZS", active=True)
    db_session.add_all([patient, service])
    db_session.flush()
    return patient, service


@pytest.mark.parametrize("creator", ["crud", "qr"])
def test_explicit_trusted_currency_and_zero_are_preserved(db_session, catalog, creator):
    patient, service = catalog
    items = [{"service_id": service.id, "name": "SYNTHETIC", "quantity": 2,
              "price": Decimal("0.00"), "currency": "USD"}]
    kwargs = {"patient_id": patient.id, "visit_date": date.today(), "services": items,
              "trusted_currency_by_service": {service.id: "UZS"}}
    if creator == "crud":
        visit = create_visit(db_session, **kwargs, commit=False, log=False)
    else:
        visit = _Qr(db_session)._create_visit_for_qr(**kwargs)
    db_session.flush()
    line = db_session.query(VisitService).filter_by(visit_id=visit.id).one()
    assert line.currency == "UZS"
    assert line.price == Decimal("0.00")
    assert line.qty == 2


@pytest.mark.parametrize("creator", ["crud", "qr"])
def test_client_currency_without_trusted_map_remains_unknown(db_session, catalog, creator):
    patient, service = catalog
    kwargs = {"patient_id": patient.id, "visit_date": date.today(),
              "services": [{"service_id": service.id, "name": "SYNTHETIC", "price": 1, "currency": "USD"}]}
    if creator == "crud":
        visit = create_visit(db_session, **kwargs, commit=False, log=False)
    else:
        visit = _Qr(db_session)._create_visit_for_qr(**kwargs)
    db_session.flush()
    assert db_session.query(VisitService).filter_by(visit_id=visit.id).one().currency is None


@pytest.mark.parametrize("creator", ["crud", "qr"])
@pytest.mark.parametrize("bad_map", [{}, {999999: "UZS"}, {"bad": "UZS"}, {1: "usd"}, {1: ""}, {1: "UZS", 999998: "USD"}])
def test_invalid_trusted_map_fails_before_any_visit(db_session, catalog, creator, bad_map):
    patient, service = catalog
    # Replace sentinel 1 with the actual generated service ID.
    mapped = {service.id if key == 1 else key: value for key, value in bad_map.items()}
    before = db_session.query(Visit).count()
    kwargs = {"patient_id": patient.id, "visit_date": date.today(),
              "services": [{"service_id": service.id, "name": "SYNTHETIC", "price": 1}],
              "trusted_currency_by_service": mapped}
    with pytest.raises(ValueError):
        if creator == "crud":
            create_visit(db_session, **kwargs, commit=False, log=False)
        else:
            _Qr(db_session)._create_visit_for_qr(**kwargs)
    assert db_session.query(Visit).count() == before


@pytest.mark.integration
def test_postgres_helpers_persist_only_explicit_trusted_currency():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    schema = "currency_helper_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            patient = Patient(first_name="SYNTHETIC", last_name="Currency")
            service = Service(code="SYNTHETIC-CURRENCY-PG", name="SYNTHETIC", price=Decimal("0.07"),
                              currency="UZS", active=True)
            db.add_all([patient, service])
            db.flush()
            items = [{"service_id": service.id, "name": "SYNTHETIC", "quantity": 3, "price": Decimal("0.07")}]
            kwargs = {"patient_id": patient.id, "visit_date": date.today(), "services": items,
                      "trusted_currency_by_service": {service.id: "UZS"}}
            visits = [create_visit(db, **kwargs, commit=False, log=False), _Qr(db)._create_visit_for_qr(**kwargs)]
            db.commit()
            lines = db.query(VisitService).filter(VisitService.visit_id.in_([visit.id for visit in visits])).all()
            assert len(lines) == 2
            assert all((line.currency, line.price, line.qty) == ("UZS", Decimal("0.07"), 3) for line in lines)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
