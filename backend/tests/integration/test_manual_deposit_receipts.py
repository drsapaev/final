"""Verify durable manual deposit commands using synthetic staff and ledger data."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from json import dumps
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.force_majeure import AddDepositRequest
from app.models.patient import Patient
from app.models.refund_deposit import DepositTransaction, PatientDeposit
from app.models.user import User
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from tests.conftest import mint_access_token
from tests.integration.test_deposit_refund_evidence_pg import install_deposit_guards
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401

PREFIX = "/api/v1/force-majeure/deposits"


def _body(patient_id: int, amount: str) -> dict:
    return {"patient_id": patient_id, "amount": amount, "client_request_id": str(uuid4())}


@pytest.mark.parametrize("action", ("add", "use"))
def test_manual_deposit_requires_exact_amount_and_uuid(client, auth_headers, test_patient, action):
    path = f"{PREFIX}/{action}"
    patient_id = test_patient.id
    assert client.post(path, headers=auth_headers, json={"patient_id": patient_id, "amount": "1.00"}).status_code == 422
    for amount in ("0", "1.001", "10000000000.00", "Infinity"):
        assert client.post(path, headers=auth_headers, json=_body(patient_id, amount)).status_code == 422
    invalid = _body(patient_id, "1.00") | {"client_request_id": "synthetic-not-a-uuid"}
    assert client.post(path, headers=auth_headers, json=invalid).status_code == 422


@pytest.mark.parametrize("action", ["add", "use"])
def test_http_deposit_rejects_subcent_json_before_writing(
    client, db_session, auth_headers, test_patient, action,
):
    patient_id = test_patient.id
    funding = _body(patient_id, "20.25") | {"amount": 20.25}
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=funding).status_code == 200
    amount = "1.00000000000000000001"
    raw_body = dumps(_body(patient_id, amount)).replace(dumps(amount), amount)
    result = client.post(
        f"{PREFIX}/{action}",
        headers={**auth_headers, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert result.status_code == 422
    db_session.expire_all()
    balance = db_session.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id))
    assert balance == Decimal("20.25")
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_credit_and_debit_replay_original_balances(client, db_session, auth_headers, test_visit):
    patient_id = test_visit.patient_id
    credit = _body(patient_id, "100.00")
    debit = _body(patient_id, "80.00") | {"visit_id": test_visit.id}

    def apply(action, body):
        response = client.post(f"{PREFIX}/{action}", headers=auth_headers, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    credited = apply("add", credit)
    debited = apply("use", debit)
    later = apply("add", _body(patient_id, "5.00"))
    assert (credited["balance"], debited["balance"], later["balance"]) == (100, 20, 25)
    assert apply("add", credit) == credited
    assert apply("use", debit) == debited
    db_session.expire_all()
    deposit = db_session.scalar(select(PatientDeposit).filter_by(patient_id=patient_id))
    entries = db_session.scalars(select(DepositTransaction).filter_by(deposit_id=deposit.id)).all()
    assert deposit.balance == Decimal("25.00")
    assert len(entries) == len({entry.client_request_id for entry in entries}) == 3
    assert all(entry.command_currency == "UZS" and entry.command_is_active for entry in entries)


def test_deposit_key_reuse_cannot_change_amount_or_action(client, db_session, auth_headers, test_patient):
    credit = _body(test_patient.id, "20.00")
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=credit).status_code == 200
    for action, body in (("add", credit | {"amount": "21.00"}), ("use", credit)):
        response = client.post(f"{PREFIX}/{action}", headers=auth_headers, json=body)
        assert response.status_code == 409
        assert response.json() == {"detail": "Параметры депозитной операции не совпадают"}
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_deposit_replay_requires_the_original_cashier(client, db_session, auth_headers, test_patient):
    credit = _body(test_patient.id, "20.00")
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=credit).status_code == 200
    cashier = User(username="synthetic-other-deposit-cashier", hashed_password="!", role="Cashier", is_active=True)
    db_session.add(cashier)
    db_session.commit()
    other_headers = {"Authorization": f"Bearer {mint_access_token(cashier)}"}
    other_operation = client.post(f"{PREFIX}/add", headers=other_headers, json=_body(test_patient.id, "5.00"))
    assert other_operation.status_code == 200, other_operation.text
    response = client.post(f"{PREFIX}/add", headers=other_headers, json=credit)
    assert response.status_code == 409
    assert response.json() == {"detail": "Параметры депозитной операции не совпадают"}
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 2


@pytest.fixture
def manual_deposit_pg(guarded_pg):
    owner, runtime, ids = guarded_pg
    schema_name = owner.dialect.default_schema_name
    quote = owner.dialect.identifier_preparer.quote_identifier
    schema, role = quote(schema_name), quote(runtime.url.username)
    with owner.begin() as conn:
        install_deposit_guards(conn, schema_name)
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.patient_deposits TO {role}")
        conn.exec_driver_sql(f"GRANT UPDATE (balance, updated_at) ON {schema}.patient_deposits TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.deposit_transactions TO {role}")
        conn.exec_driver_sql(
            f"GRANT USAGE ON SEQUENCE {schema}.patient_deposits_id_seq, {schema}.deposit_transactions_id_seq TO {role}"
        )
    return owner, runtime, ids


def test_concurrent_retries_create_only_one_deposit_credit(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    command = AddDepositRequest(**_body(ids["patient"], "25.00"))
    start = Barrier(2)

    def apply():
        with Session(runtime) as db:
            start.wait(timeout=5)
            return ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(apply), pool.submit(apply)
        assert first.result(timeout=12) == second.result(timeout=12)
    with Session(owner) as db:
        receipt = db.scalars(select(DepositTransaction).filter_by(client_request_id=command.client_request_id)).one()
        assert receipt.deposit.balance == receipt.balance_after == Decimal("25.00")
        assert receipt.performed_by == ids["stage"]


def test_deposit_key_race_rolls_back_the_other_patients_balance(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    with Session(owner, expire_on_commit=False) as db:
        other = Patient(first_name="SYNTHETIC", last_name="SECOND DEPOSIT")
        db.add(other)
        db.commit()
        subjects = (ids["patient"], other.id)
    request_id = uuid4()
    ready = Barrier(2)

    class RacingRepository(ForceMajeureApiRepository):
        def commit(self) -> None:
            ready.wait(timeout=5)
            super().commit()

    def apply(patient_id):
        command = AddDepositRequest(patient_id=patient_id, amount=Decimal("25.00"), client_request_id=request_id)
        with Session(runtime) as db:
            service = ForceMajeureApiService(db, repository=RacingRepository(db))
            try:
                service.add_to_deposit(request=command, current_user_id=ids["stage"])
                return 200
            except ForceMajeureApiDomainError as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(apply, subjects)) == [200, 409]
    with Session(owner) as db:
        [deposit] = db.scalars(select(PatientDeposit).where(PatientDeposit.patient_id.in_(subjects))).all()
        assert deposit.balance == Decimal("25.00")
        assert db.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_manual_deposit_receipt_is_immutable_and_prevents_downgrade(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    command = AddDepositRequest(**_body(ids["patient"], "25.00"))
    with Session(runtime) as db:
        ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])
    with owner.connect() as conn:
        receipt_id = conn.scalar(select(DepositTransaction.id).filter_by(client_request_id=command.client_request_id))
    for statement in (
        "UPDATE deposit_transactions SET amount=1 WHERE id=:id",
        "DELETE FROM deposit_transactions WHERE id=:id",
    ):
        with pytest.raises(DBAPIError, match="immutable manual deposit receipt"), owner.begin() as conn:
            conn.execute(text(statement), {"id": receipt_id})
    migration = _migration("0137_deposit_manual_receipts.py")
    with pytest.raises(DBAPIError, match="manual deposit receipts prevent downgrade"), owner.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.downgrade()
