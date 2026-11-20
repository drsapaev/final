"""Exact benefit evidence validation, independent of user authorization."""

from copy import deepcopy
from decimal import Decimal, localcontext

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError

from app.db.base_class import Base
from app.services.encounter_benefit_net import (
    BenefitQuoteError,
    _snapshot_digest,
    validate_benefit_snapshot,
)
from tests.integration.test_encounter_migration_pg import _migration


@pytest.fixture
def evidence():
    return {
        "visible": True,
        "selected": {"id": 1, "patient": 7, "encounter": 5},
        "encounter": {"id": 5, "patient": 7, "generation": 42, "provenance": "new"},
        "visits": [{"id": 1, "patient": 7, "encounter": 5, "epoch": 10},
                   {"id": 2, "patient": 7, "encounter": 5, "epoch": 11}],
        "lines": [{"id": 101, "visit": 1, "service": 20, "qty": 3, "price": "0.07", "currency": "UZS"},
                  {"id": 102, "visit": 2, "service": 21, "qty": 1, "price": "0.05", "currency": "UZS"}],
        "applications": [{"id": 9, "encounter": 5, "patient": 7, "generation": 42,
                          "gross": "0.21", "discount": "0.10", "net": "0.11"}],
        "snapshots": [{"app": 9, "visit": 1, "visit_snapshot": 1, "patient": 7, "encounter": 5, "epoch": 10},
                      {"app": 9, "visit": 2, "visit_snapshot": 2, "patient": 7, "encounter": 5, "epoch": 11}],
        "allocations": [{"app": 9, "visit": 1, "visit_snapshot": 1, "line": 101, "line_snapshot": 101,
                         "service": 20, "epoch": 10, "qty": 3, "unit": "0.07", "gross": "0.21",
                         "discount": "0.10", "net": "0.11"}],
        "events": [],
    }


def test_quantity_discount_is_aggregate_exact_not_rounded_per_unit(evidence):
    quote = validate_benefit_snapshot(evidence, visit_id=1)
    assert quote.total == Decimal("0.11")
    assert quote.line_totals == {101: Decimal("0.11")}
    sibling = deepcopy(evidence)
    sibling["selected"]["id"] = 2
    assert validate_benefit_snapshot(sibling, visit_id=2).total == Decimal("0.05")


def test_validation_does_not_inherit_a_low_decimal_precision(evidence):
    with localcontext() as context:
        context.prec = 2
        quote = validate_benefit_snapshot(evidence, visit_id=1)
    assert quote.total == Decimal("0.11")
    assert quote.line_totals == {101: Decimal("0.11")}


def test_snapshot_digest_binds_complete_evidence_independent_of_row_order(evidence):
    baseline = _snapshot_digest(evidence)
    reordered = deepcopy(evidence)
    reordered["visits"].reverse()
    reordered["lines"].reverse()
    assert _snapshot_digest(reordered) == baseline
    reordered["lines"][0]["price"] = "0.06"
    assert _snapshot_digest(reordered) != baseline


@pytest.mark.parametrize("mutate", [
    lambda e: e["snapshots"].pop(),
    lambda e: e["visits"][1].update(epoch=12),  # even an ineligible Visit
    lambda e: e["encounter"].update(generation=43),
    lambda e: e["allocations"][0].update(visit=None),
    lambda e: e["allocations"][0].update(qty=2),
    lambda e: e["allocations"][0].update(net="0.12"),
    lambda e: e["allocations"].append(deepcopy(e["allocations"][0])),
    lambda e: e["events"].append({"app": 9, "kind": "voided"}),
    lambda e: e.update(visible=False),
])
def test_stale_incomplete_or_invisible_evidence_never_grants(evidence, mutate):
    mutate(evidence)
    with pytest.raises(BenefitQuoteError):
        validate_benefit_snapshot(evidence, visit_id=1)


def test_no_application_is_distinct_from_invisible_history(evidence):
    evidence["applications"] = []
    assert validate_benefit_snapshot(evidence, visit_id=1) is None
    evidence["visible"] = False
    with pytest.raises(BenefitQuoteError):
        validate_benefit_snapshot(evidence, visit_id=1)


def test_sqlite_real_migration_retains_identity_and_refuses_evidence_downgrade():
    engine = create_engine("sqlite:///:memory:")
    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            # create_all is newer than 0125; reconstruct its predecessor and
            # execute the actual migration rather than approximating triggers.
            conn.execute(text("DROP TABLE encounter_benefit_visit_snapshots"))
            conn.execute(text("DROP INDEX uq_enc_benefit_app_identity"))
            migration = _migration("0125_benefit_visibility.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            foreign_keys = conn.exec_driver_sql("PRAGMA foreign_key_list(encounter_benefit_visit_snapshots)").all()
            targets = {row[2] for row in foreign_keys}
            assert {"visits", "encounter_benefit_applications"}.issubset(targets)
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text("""INSERT INTO encounter_benefit_visit_snapshots
                  (application_id,visit_id,encounter_id,patient_id,visit_id_snapshot,visit_context_epoch)
                  VALUES (999,123,456,789,123,1)"""))
                # Deferred composite FKs are checked at savepoint release.
            migration.downgrade()
            migration.upgrade()
    finally:
        engine.dispose()
