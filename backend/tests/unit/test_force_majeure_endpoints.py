"""HTTP-level contract for the force-majeure endpoints — #3809 round 3.

Pins (review round 2 → round 3):

* P2 (force_majeure.py GET preview): queue-validation domain errors map
  to 404/422 at the HTTP layer — before round 3 the new GET preview let
  ``ForceMajeureApiDomainError`` escape as an unhandled 500.
* P1 (preview set binding): the bound mutations surface the
  post-preview drift refusal as HTTP 409, and a confirmed happy path
  moves money exactly once per payment.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.refund_deposit import DepositTransaction, PatientDeposit
from app.models.visit import Visit

PREVIEW_PATH = "/api/v1/force-majeure/pending-entries"
TRANSFER_PATH = "/api/v1/force-majeure/transfer"
CANCEL_PATH = "/api/v1/force-majeure/cancel-with-refund"


def _seed_bound_queue(db_session, test_doctor, test_patient, *, entries=2):
    """Doctor-owned queue + N waiting entries with a paid payment each."""
    today = date.today()
    queue = DailyQueue(
        day=today,
        specialist_id=test_doctor.id,
        queue_tag="fm_endpoints_queue",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    made_entries = []
    payments = []
    for number in range(1, entries + 1):
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time=f"1{number}:00",
            status="open",
            discount_mode="none",
            department="cardiology",
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal(f"{100 + number}.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            visit_id=visit.id,
            number=number,
            patient_id=test_patient.id,
            patient_name=f"Endpoint Patient {number}",
            status="waiting",
            source="desk",
        )
        db_session.add_all([payment, entry])
        db_session.flush()
        made_entries.append(entry)
        payments.append(payment)
    db_session.commit()
    return queue, made_entries, payments


@pytest.mark.unit
class TestForceMajeureEndpoints:
    def test_get_preview_unknown_queue_is_404_not_500(
        self, client, db_session, test_doctor, registrar_auth_headers
    ):
        """Round 3 P2: an unknown queue id is a domain 404, not a crash."""
        response = client.get(
            PREVIEW_PATH,
            params={
                "specialist_id": test_doctor.id,
                "target_date": date.today(),
                "daily_queue_id": 999999,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 404, response.text[:300]

    def test_get_preview_day_mismatch_is_422_not_500(
        self, client, db_session, test_doctor, registrar_auth_headers
    ):
        other_day_queue = DailyQueue(
            day=date.today() + timedelta(days=3),
            specialist_id=test_doctor.id,
            queue_tag="fm_other_day_queue",
            active=True,
        )
        db_session.add(other_day_queue)
        db_session.commit()

        response = client.get(
            PREVIEW_PATH,
            params={
                "specialist_id": test_doctor.id,
                "target_date": date.today(),
                "daily_queue_id": other_day_queue.id,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 422, response.text[:300]

    def test_get_preview_foreign_specialist_queue_is_422_not_500(
        self, client, db_session, test_doctor, registrar_auth_headers
    ):
        foreign_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id + 1000,
            queue_tag="fm_foreign_queue",
            active=True,
        )
        db_session.add(foreign_queue)
        db_session.commit()

        response = client.get(
            PREVIEW_PATH,
            params={
                "specialist_id": test_doctor.id,
                "target_date": date.today(),
                "daily_queue_id": foreign_queue.id,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 422, response.text[:300]

    def test_get_preview_bound_returns_exactly_that_queue(
        self, client, db_session, test_doctor, test_patient, registrar_auth_headers
    ):
        queue, entries, _payments = _seed_bound_queue(
            db_session, test_doctor, test_patient, entries=2
        )
        other_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="fm_other_endpoint_queue",
            active=True,
        )
        db_session.add(other_queue)
        db_session.flush()
        stranger = OnlineQueueEntry(
            queue_id=other_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Stranger Patient",
            status="waiting",
            source="desk",
        )
        db_session.add(stranger)
        db_session.commit()

        response = client.get(
            PREVIEW_PATH,
            params={
                "specialist_id": test_doctor.id,
                "target_date": date.today(),
                "daily_queue_id": queue.id,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 200, response.text[:300]
        payload = response.json()
        assert {item["id"] for item in payload} == {entry.id for entry in entries}

    def test_transfer_drift_is_409_and_moves_nothing(
        self, client, db_session, test_doctor, test_patient, registrar_auth_headers
    ):
        """Round 3 P1: a patient joining the queue after the preview must
        not be transferred silently — the HTTP layer refuses with 409."""
        queue, entries, _payments = _seed_bound_queue(
            db_session, test_doctor, test_patient, entries=1
        )
        late_joiner = OnlineQueueEntry(
            queue_id=queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Late Joiner",
            status="waiting",
            source="desk",
        )
        db_session.add(late_joiner)
        db_session.commit()

        response = client.post(
            TRANSFER_PATH,
            json={
                "specialist_id": test_doctor.id,
                "target_date": str(date.today()),
                "daily_queue_id": queue.id,
                "expected_entry_ids": [entries[0].id],
                "reason": "doctor emergency at the desk",
                "send_notifications": False,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 409, response.text[:300]
        assert "предпросмотра" in response.json()["detail"]

        db_session.refresh(entries[0])
        db_session.refresh(late_joiner)
        assert entries[0].status == "waiting"
        assert late_joiner.status == "waiting"
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .count()
            == 0
        )

    def test_bound_cancel_happy_path_and_replay_refuse(
        self, client, db_session, test_doctor, test_patient, registrar_auth_headers
    ):
        """End-to-end through HTTP: the confirmed snapshot cancels exactly
        its entries, credits each payment exactly once, and the SAME
        replayed confirmation is refused with 409 — no double refund."""
        queue, entries, payments = _seed_bound_queue(
            db_session, test_doctor, test_patient, entries=2
        )
        snapshot = [entry.id for entry in entries]
        confirmation = {
            "specialist_id": test_doctor.id,
            "target_date": str(date.today()),
            "daily_queue_id": queue.id,
            "expected_entry_ids": snapshot,
            "reason": "doctor emergency at the desk",
            "refund_type": "deposit",
            "send_notifications": False,
        }

        response = client.post(
            CANCEL_PATH, json=confirmation, headers=registrar_auth_headers
        )
        assert response.status_code == 200, response.text[:300]
        assert response.json()["cancelled"] == 2

        for payment in payments:
            credits = (
                db_session.query(DepositTransaction)
                .filter(DepositTransaction.payment_id == payment.id)
                .count()
            )
            assert credits == 1, payment.id

        deposit = (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .one()
        )
        assert deposit.balance == sum(p.amount for p in payments)

        # The SAME confirmation replayed (double-submit / retry): the
        # live pending set is now empty → drift → 409, money untouched.
        replay = client.post(
            CANCEL_PATH, json=confirmation, headers=registrar_auth_headers
        )
        assert replay.status_code == 409, replay.text[:300]

        db_session.refresh(deposit)
        assert deposit.balance == sum(p.amount for p in payments)
        for payment in payments:
            assert (
                db_session.query(DepositTransaction)
                .filter(DepositTransaction.payment_id == payment.id)
                .count()
                == 1
            )

    def test_missing_snapshot_is_rejected_at_the_http_layer(
        self, client, db_session, test_doctor, test_patient, registrar_auth_headers
    ):
        """A bound POST without the preview snapshot is a 422 — the
        unbounded whole-queue mutation must not be reachable."""
        queue, _entries, _payments = _seed_bound_queue(
            db_session, test_doctor, test_patient, entries=1
        )

        response = client.post(
            TRANSFER_PATH,
            json={
                "specialist_id": test_doctor.id,
                "target_date": str(date.today()),
                "daily_queue_id": queue.id,
                "reason": "doctor emergency at the desk",
                "send_notifications": False,
            },
            headers=registrar_auth_headers,
        )
        assert response.status_code == 422, response.text[:300]
        assert "expected_entry_ids" in response.json()["detail"]
