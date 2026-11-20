"""Discount quota and audit checks using only synthetic transactions."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.discount_benefits import Discount, DiscountApplication, DiscountType
from app.models.user import User
from app.services.discount_benefits_service import DiscountBenefitsService

pytestmark = pytest.mark.integration


@pytest.fixture
def discount_db(kind, tmp_path):
    if kind == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'discount-use.sqlite'}")
        admin, schema = None, None
    else:
        url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
        if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
            pytest.skip("requires an explicitly disposable clinic_test PostgreSQL database")
        admin = create_engine(url)
        schema = "discount_use_" + uuid4().hex
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=12000"})

    try:
        Base.metadata.create_all(engine, tables=[User.__table__, Discount.__table__, DiscountApplication.__table__])
        with Session(engine) as db:
            item = Discount(name="Synthetic last discount", discount_type=DiscountType.PERCENTAGE,
                            value=10, usage_limit=1, usage_count=0, is_active=True)
            db.add(item)
            db.flush()
            ident = item.id
            db.commit()
        yield engine, ident
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


def _usage(db, ident):
    count = db.scalar(select(Discount.usage_count).where(Discount.id == ident))
    rows = db.scalar(select(func.count(DiscountApplication.id)).where(DiscountApplication.discount_id == ident))
    return count, rows


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_audit_failure_rolls_back_discount_application(discount_db):
    engine, ident = discount_db
    with Session(engine) as db:
        @event.listens_for(db, "after_flush", once=True)
        def fail_after_writes(session, _):
            assert _usage(session, ident) == (1, 1)
            raise RuntimeError("synthetic audit transaction failure")

        service = DiscountBenefitsService(db)
        with pytest.raises(RuntimeError, match="synthetic audit transaction failure"):
            service.apply_discount(ident, 100)
        assert not db.in_transaction()
        assert _usage(db, ident) == (0, 0)
        result = service.apply_discount(ident, 100)
        assert (result.discount_amount, result.final_amount) == (10, 90)
        with pytest.raises(ValueError, match="Скидка недоступна"):
            service.apply_discount(ident, 100)
        assert _usage(db, ident) == (1, 1)


@pytest.mark.parametrize("kind", ["sqlite"])
def test_ineligible_discount_does_not_consume_quota(discount_db):
    engine, ident = discount_db
    with Session(engine) as db:
        db.get(Discount, ident).min_amount = 100
        db.commit()
        service = DiscountBenefitsService(db)
        for amount in (50, float("inf")):
            with pytest.raises(ValueError):
                service.apply_discount(ident, amount)
        assert _usage(db, ident) == (0, 0)


@pytest.mark.parametrize("kind", ["postgresql"])
def test_concurrent_discount_applications_share_last_quota(discount_db):
    engine, ident = discount_db
    acquired, proceed, started = Event(), Event(), Event()
    competing_pid = []

    class HeldDiscount(DiscountBenefitsService):
        def calculate_discount(self, discount, amount, quantity=1):
            acquired.set()
            assert proceed.wait(15)
            return super().calculate_discount(discount, amount, quantity)

    def first_application():
        with Session(engine) as db:
            return HeldDiscount(db).apply_discount(ident, 100).discount_amount

    def second_application():
        with Session(engine) as db:
            competing_pid.append(db.scalar(text("SELECT pg_catalog.pg_backend_pid()")))
            stale = db.get(Discount, ident)
            assert stale.usage_count == 0
            started.set()
            return DiscountBenefitsService(db).apply_discount(ident, 100).discount_amount

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_application)
        try:
            assert acquired.wait(5)
            second = pool.submit(second_application)
            assert started.wait(5)
            deadline = monotonic() + 5
            with engine.connect() as monitor:
                while monotonic() < deadline:
                    blocked = monitor.scalar(text("SELECT cardinality(pg_catalog.pg_blocking_pids(:pid))"),
                                             {"pid": competing_pid[0]})
                    if blocked:
                        break
                    sleep(0.01)
                else:
                    pytest.fail("second application never waited on the held discount row")
        finally:
            proceed.set()
        assert first.result(timeout=5) == 10
        with pytest.raises(ValueError, match="Скидка недоступна"):
            second.result(timeout=5)

    with Session(engine) as db:
        assert _usage(db, ident) == (1, 1)
