from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.appointment import Appointment
from app.models.payment_webhook import PaymentWebhook
from app.repositories.analytics_simple_repository import AnalyticsSimpleRepository


@pytest.mark.unit
class TestAnalyticsSimpleRepository:
    def test_counts_and_date_filter_increase_after_insert(self, db_session, test_patient):
        repository = AnalyticsSimpleRepository(db_session)
        today = date.today()
        tomorrow = today + timedelta(days=1)

        before_patients = repository.count_patients()
        before_appointments = repository.count_appointments()
        before_today_appointments = repository.count_appointments_for_date(today)
        before_payments = repository.count_payments()

        db_session.add_all(
            [
                Appointment(
                    patient_id=test_patient.id,
                    appointment_date=today,
                    appointment_time="10:00",
                    status="scheduled",
                ),
                Appointment(
                    patient_id=test_patient.id,
                    appointment_date=tomorrow,
                    appointment_time="11:00",
                    status="scheduled",
                ),
                PaymentWebhook(
                    provider="click",
                    webhook_id="analytics_simple_wh_click",
                    transaction_id="analytics_simple_trx_click",
                    status="pending",
                    amount=1000,
                    currency="UZS",
                    raw_data={"source": "unit"},
                ),
                PaymentWebhook(
                    provider="payme",
                    webhook_id="analytics_simple_wh_payme",
                    transaction_id="analytics_simple_trx_payme",
                    status="processed",
                    amount=2000,
                    currency="UZS",
                    raw_data={"source": "unit"},
                ),
            ]
        )
        db_session.commit()

        assert repository.count_patients() >= before_patients
        assert repository.count_appointments() == before_appointments + 2
        assert (
            repository.count_appointments_for_date(today) == before_today_appointments + 1
        )
        assert repository.count_payments() == before_payments + 2

    def test_list_appointment_trends_returns_grouped_counts(self, db_session, test_patient):
        repository = AnalyticsSimpleRepository(db_session)
        today = date.today()
        tomorrow = today + timedelta(days=1)

        baseline_rows = repository.list_appointment_trends(
            start_date=today,
            end_date=tomorrow,
        )
        baseline = {row.date: row.count for row in baseline_rows}

        db_session.add_all(
            [
                Appointment(
                    patient_id=test_patient.id,
                    appointment_date=today,
                    appointment_time="12:00",
                    status="scheduled",
                ),
                Appointment(
                    patient_id=test_patient.id,
                    appointment_date=tomorrow,
                    appointment_time="13:00",
                    status="scheduled",
                ),
            ]
        )
        db_session.commit()

        rows = repository.list_appointment_trends(start_date=today, end_date=tomorrow)
        grouped = {row.date: row.count for row in rows}

        assert grouped[today] == baseline.get(today, 0) + 1
        assert grouped[tomorrow] == baseline.get(tomorrow, 0) + 1
