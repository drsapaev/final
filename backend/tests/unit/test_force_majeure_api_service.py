from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.refund_deposit import DepositTransaction, PatientDeposit, RefundType
from app.models.visit import Visit
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from app.services.force_majeure_service import (
    ForceMajeureError,
    ForceMajeureService,
    get_force_majeure_service,
)


@pytest.mark.unit
class TestForceMajeureApiService:
    def test_transfer_entry_ids_are_scoped_to_requested_specialist_and_date(
        self, monkeypatch
    ):
        captured = {}
        selected_entries = [SimpleNamespace(id=11)]

        class Repository:
            db = object()

            def list_pending_entries_by_ids(
                self, entry_ids, *, specialist_id, target_date
            ):
                captured["entry_ids"] = entry_ids
                captured["specialist_id"] = specialist_id
                captured["target_date"] = target_date
                return selected_entries

        force_service = SimpleNamespace(
            transfer_entries_to_tomorrow=lambda **kwargs: {
                "success": True,
                "transferred_ids": [entry.id for entry in kwargs["entries"]],
            }
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: force_service,
        )

        target_date = date.today()
        service = ForceMajeureApiService(db=None, repository=Repository())
        result = service.transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                entry_ids=[11, 12],
                specialist_id=77,
                target_date=target_date,
                daily_queue_id=None,
                reason="doctor emergency",
                send_notifications=False,
            ),
            current_user_id=10,
        )

        assert result["success"] is True
        assert captured == {
            "entry_ids": [11, 12],
            "specialist_id": 77,
            "target_date": target_date,
        }

    def test_repository_filters_explicit_entry_ids_by_specialist_and_date(
        self, db_session, test_doctor, test_patient
    ):
        today = date.today()
        other_day = today + timedelta(days=1)
        requested_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        other_specialist_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id + 1000,
            queue_tag="dermatology_common",
            active=True,
        )
        other_day_queue = DailyQueue(
            day=other_day,
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add_all([requested_queue, other_specialist_queue, other_day_queue])
        db_session.flush()

        scoped_entry = OnlineQueueEntry(
            queue_id=requested_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Scoped Patient",
            status="waiting",
            source="desk",
        )
        other_specialist_entry = OnlineQueueEntry(
            queue_id=other_specialist_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Other Specialist",
            status="waiting",
            source="desk",
        )
        other_day_entry = OnlineQueueEntry(
            queue_id=other_day_queue.id,
            number=3,
            patient_id=test_patient.id,
            patient_name="Other Day",
            status="waiting",
            source="desk",
        )
        db_session.add_all([scoped_entry, other_specialist_entry, other_day_entry])
        db_session.flush()

        entries = ForceMajeureApiRepository(db_session).list_pending_entries_by_ids(
            [scoped_entry.id, other_specialist_entry.id, other_day_entry.id],
            specialist_id=test_doctor.id,
            target_date=today,
        )

        assert [entry.id for entry in entries] == [scoped_entry.id]

    # -- Review round 2 (#3809 P1): queue identity binding -----------------

    def test_pending_entries_bind_to_requested_daily_queue_not_registry_surface(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """The registrar row's canonical daily_queue_id is the ONLY target.

        The doctor's specialty tag has a registry-backed resource surface
        (the shadow-queue case): the legacy specialist resolution prefers it
        and would return ANOTHER queue's patients. Bound to daily_queue_id
        the preview returns exactly the row's own queue entries.
        """
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        resource = QueueResource(
            code="cardio_surface",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        surface_queue = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_own_queue",
            active=True,
        )
        db_session.add_all([surface_queue, doctor_queue])
        db_session.flush()

        doctor_entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Doctor Queue Patient",
            status="waiting",
            source="desk",
        )
        surface_entry = OnlineQueueEntry(
            queue_id=surface_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Surface Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([doctor_entry, surface_entry])
        db_session.flush()

        service = ForceMajeureApiService(db_session)

        bound = service.get_pending_entries(
            specialist_id=test_doctor.id,
            target_date=today,
            daily_queue_id=doctor_queue.id,
        )
        assert [entry["id"] for entry in bound] == [doctor_entry.id]

        # The legacy path (no daily_queue_id) still prefers the registry
        # surface — the exact hazard the binding removes for the UI.
        legacy = service.get_pending_entries(
            specialist_id=test_doctor.id,
            target_date=today,
        )
        assert [entry["id"] for entry in legacy] == [surface_entry.id]

    def test_pending_entries_daily_queue_id_rejects_unknown_queue(
        self, db_session, test_doctor
    ):
        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=999999,
            )
        assert exc_info.value.status_code == 404

    def test_pending_entries_daily_queue_id_rejects_foreign_specialist_queue(
        self, db_session, test_doctor
    ):
        other_specialist_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id + 1000,
            queue_tag="foreign_queue",
            active=True,
        )
        db_session.add(other_specialist_queue)
        db_session.flush()

        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=other_specialist_queue.id,
            )
        assert exc_info.value.status_code == 422

    def test_pending_entries_daily_queue_id_rejects_day_mismatch(
        self, db_session, test_doctor
    ):
        other_day_queue = DailyQueue(
            day=date.today() + timedelta(days=3),
            specialist_id=test_doctor.id,
            queue_tag="future_day_queue",
            active=True,
        )
        db_session.add(other_day_queue)
        db_session.flush()

        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=other_day_queue.id,
            )
        assert exc_info.value.status_code == 422

    def test_daily_queue_id_and_entry_ids_are_mutually_exclusive(self, monkeypatch):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        with pytest.raises(ForceMajeureApiDomainError) as transfer_error:
            service.transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=5,
                    entry_ids=[1, 2],
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert transfer_error.value.status_code == 422

        with pytest.raises(ForceMajeureApiDomainError) as cancel_error:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=5,
                    entry_ids=[1, 2],
                    reason="reason",
                    refund_type="deposit",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert cancel_error.value.status_code == 422

    def test_transfer_passes_resolved_source_day_to_domain_service(self, monkeypatch):
        captured = {}

        def fake_transfer(**kwargs):
            captured.update(kwargs)
            return {"success": True, "transferred": len(kwargs["entries"])}

        force_service = SimpleNamespace(
            get_pending_entries=lambda **kwargs: [SimpleNamespace(id=11)],
            transfer_entries_to_tomorrow=fake_transfer,
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: force_service,
        )

        source_day = date(2026, 11, 5)
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        service.transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=7,
                target_date=source_day,
                daily_queue_id=None,
                entry_ids=None,
                reason="doctor absent on Nov 5",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        # round 2 P1: the destination day must derive from the SOURCE queue
        # day, never from the current clinic day
        assert captured["source_date"] == source_day

    def test_transfer_destination_is_source_day_plus_one_for_future_queue(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """A future-dated queue transfers to source day + 1, not clinic
        tomorrow: on clinic day 2026-10-30 the Nov 5 queue moves to Nov 6
        (the old behavior recreated the entries on Oct 31 — backwards)."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        clinic_day = date(2026, 10, 30)
        monkeypatch.setattr(
            "app.services.force_majeure_service.clinic_today", lambda db: clinic_day
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.clinic_today",
            lambda db: clinic_day,
        )

        source_day = date(2026, 11, 5)
        source_queue = DailyQueue(
            day=source_day,
            specialist_id=test_doctor.id,
            queue_tag="doctor_future_queue",
            active=True,
        )
        db_session.add(source_queue)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=source_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Future Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add(entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=source_day,
                daily_queue_id=source_queue.id,
                entry_ids=None,
                expected_entry_ids=[entry.id],
                reason="doctor absent on Nov 5",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        assert result["new_date"] == "2026-11-06"
        db_session.refresh(entry)
        assert entry.status == "cancelled"
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        assert moved_queue.day == date(2026, 11, 6)

    def test_transfer_doctor_owned_row_keeps_doctor_owned_destination(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 7 (P1 destination owner): the registrar's
        doctor-owned canonical row transfers ONLY into the doctor-owned
        tomorrow queue. The registry surface of the same specialty tag
        lives on BOTH days — the old destination re-resolution would
        capture the doctor's patients into the shared resource queue."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        resource = QueueResource(
            code="cardio_surface_r7",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        # both surfaces live on the SOURCE day (round-2 two-surface setup)
        surface_today = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_own_queue_r7",
            active=True,
        )
        # the trap: the registry surface ALREADY exists on the destination
        # day — the registry-first re-resolution would pick it
        surface_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        db_session.add_all([surface_today, doctor_queue, surface_tomorrow])
        db_session.flush()

        doctor_entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Doctor Queue Patient R7",
            status="waiting",
            source="desk",
        )
        surface_entry = OnlineQueueEntry(
            queue_id=surface_today.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Surface Queue Patient R7",
            status="waiting",
            source="desk",
        )
        db_session.add_all([doctor_entry, surface_entry])
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=doctor_queue.id,
                entry_ids=None,
                expected_entry_ids=[doctor_entry.id],
                reason="doctor absent r7",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        # the destination keeps the DOCTOR owner — never the registry surface
        assert moved_queue.day == tomorrow
        assert moved_queue.specialist_id == test_doctor.id
        assert moved_queue.queue_resource_id is None
        assert moved_queue.id != surface_tomorrow.id
        # 3808 review round 8 (P1 queue tag): the destination keeps the
        # source TAG as well — the doctor's own surface is not silently
        # re-labeled as the specialty-derived consultation queue
        assert moved_queue.queue_tag == "doctor_own_queue_r7"
        # the shared resource queue on tomorrow stayed untouched
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == surface_tomorrow.id)
            .count()
            == 0
        )
        # worklist visibility: the registrar's bound preview of the new
        # doctor-owned tomorrow row shows the transferred patient
        visible = ForceMajeureApiService(db_session).get_pending_entries(
            specialist_id=test_doctor.id,
            target_date=tomorrow,
            daily_queue_id=moved_queue.id,
        )
        assert [entry["id"] for entry in visible] == [moved.id]

    def test_transfer_doctor_owned_two_tags_keep_entries_in_matching_queue(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 8 (P1 queue tag): у одного врача в один день
        сосуществуют активные очереди РАЗНЫХ тегов
        (``uq_daily_queues_active_doctor_day_tag`` — консультация и ЭКГ
        кардиолога). Перенос канонической ЭКГ-строки обязан привести
        пациентов в ЭКГ-очередь следующего дня (созданную, если её нет), а
        не в очередь консультаций того же врача; очередь консультаций не
        затрагивается."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        ecg_source = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="ecg_r8",
            active=True,
        )
        # ловушка round 8: завтра у врача УЖЕ есть АКТИВНАЯ очередь другого
        # тега — прежний поиск по (specialist_id, day) уходил именно в неё
        consult_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag="consultation_r8",
            active=True,
        )
        db_session.add_all([ecg_source, consult_tomorrow])
        db_session.flush()

        ecg_entry = OnlineQueueEntry(
            queue_id=ecg_source.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="ECG Patient R8",
            status="waiting",
            source="desk",
        )
        db_session.add(ecg_entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=ecg_source.id,
                entry_ids=None,
                expected_entry_ids=[ecg_entry.id],
                reason="ЭКГ-аппарат сломан",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        # назначение — врачебная очередь ТОГО ЖЕ тега, что и источник
        assert moved_queue.day == tomorrow
        assert moved_queue.specialist_id == test_doctor.id
        assert moved_queue.queue_tag == "ecg_r8"
        assert moved_queue.id not in {ecg_source.id, consult_tomorrow.id}
        # очередь консультаций не тронута: ни перенесённых, ни новых записей
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == consult_tomorrow.id)
            .count()
            == 0
        )

    def test_transfer_doctor_owned_two_tags_reuse_matching_destination(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 8 (P1 queue tag), зеркальный случай: подходящая
        (день, врач, тег, active) очередь завтра УЖЕ есть — перенос
        переиспользует её, а не создаёт дубль и не уходит в очередь другого
        тега того же врача."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        ecg_source = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="ecg_r8",
            active=True,
        )
        ecg_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag="ecg_r8",
            active=True,
        )
        consult_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag="consultation_r8",
            active=True,
        )
        db_session.add_all([ecg_source, ecg_tomorrow, consult_tomorrow])
        db_session.flush()

        ecg_entry = OnlineQueueEntry(
            queue_id=ecg_source.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="ECG Patient R8b",
            status="waiting",
            source="desk",
        )
        db_session.add(ecg_entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=ecg_source.id,
                entry_ids=None,
                expected_entry_ids=[ecg_entry.id],
                reason="ЭКГ-аппарат сломан",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        # переиспользована существующая ЭКГ-очередь следующего дня
        assert moved.queue_id == ecg_tomorrow.id
        assert db_session.get(DailyQueue, moved.queue_id).queue_tag == "ecg_r8"
        # дубля врачебной ЭКГ-очереди не появилось
        assert (
            db_session.query(DailyQueue)
            .filter(
                DailyQueue.day == tomorrow,
                DailyQueue.specialist_id == test_doctor.id,
                DailyQueue.queue_tag == "ecg_r8",
                DailyQueue.active.is_(True),
            )
            .count()
            == 1
        )
        # очередь консультаций не тронута
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == consult_tomorrow.id)
            .count()
            == 0
        )

    def test_transfer_doctor_owned_untagged_source_stays_untagged(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 8 (P1 queue tag), NULL-тег: источник без тега
        (batch-писатели создают такие строки) переносится в NULL-тег
        врачебную очередь следующего дня — по COALESCE-ключу
        ``uq_daily_queues_active_doctor_day_tag``, а не в тегированную
        очередь консультаций того же врача."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        untagged_source = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag=None,
            active=True,
        )
        consult_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag="consultation_r8",
            active=True,
        )
        db_session.add_all([untagged_source, consult_tomorrow])
        db_session.flush()

        untagged_entry = OnlineQueueEntry(
            queue_id=untagged_source.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Untagged Patient R8",
            status="waiting",
            source="desk",
        )
        db_session.add(untagged_entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=untagged_source.id,
                entry_ids=None,
                expected_entry_ids=[untagged_entry.id],
                reason="врач отсутствует",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        # назначение — NULL-тег врачебная очередь, не консультация
        assert moved_queue.day == tomorrow
        assert moved_queue.specialist_id == test_doctor.id
        assert moved_queue.queue_tag is None
        assert moved_queue.id not in {untagged_source.id, consult_tomorrow.id}
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == consult_tomorrow.id)
            .count()
            == 0
        )

    def test_transfer_resource_owned_row_keeps_registry_destination(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 7 (P1 destination owner), mirror case: the
        resource-owned registry surface row transfers into the SAME
        registry surface tomorrow — a doctor-owned fork must not appear."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        resource = QueueResource(
            code="cardio_surface_r7b",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        surface_today = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        surface_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        db_session.add_all([surface_today, surface_tomorrow])
        db_session.flush()
        surface_entry = OnlineQueueEntry(
            queue_id=surface_today.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Surface Patient R7b",
            status="waiting",
            source="desk",
        )
        db_session.add(surface_entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=surface_today.id,
                entry_ids=None,
                expected_entry_ids=[surface_entry.id],
                reason="resource downtime r7",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        # the destination is the registry surface — owner preserved
        assert moved.queue_id == surface_tomorrow.id
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        assert moved_queue.specialist_id is None
        assert moved_queue.queue_resource_id == resource.id
        # no doctor-owned fork on the destination day
        assert (
            db_session.query(DailyQueue)
            .filter(
                DailyQueue.day == tomorrow,
                DailyQueue.specialist_id == test_doctor.id,
            )
            .all()
            == []
        )

    def test_transfer_resource_owned_source_rejects_doctor_owned_same_tag_destination(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 9 (P1 destination owner recheck): перенос с
        ресурсной очереди закрывается отказом, когда поверхность
        (day, tag) завтра занята АКТИВНОЙ врачебной очередью того же
        тега при живом реестровом ряде — tag_routes_to_resource вернёт
        именно её (queue_resource_id IS NULL, specialist_id NOT NULL),
        и ресурсные пациенты не должны молча переезжать во врачебную
        поверхность. Fail closed: источник не тронут, новых очередей
        не создано."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        resource = QueueResource(
            code="lab_surface_r9",
            queue_tag=test_doctor.specialty,
            display_name="Лаборатория (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        source_today = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        # завтра (day, tag) уже занят ВРАЧЕБНОЙ очередью того же тега
        doctor_queue_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        db_session.add_all([source_today, doctor_queue_tomorrow])
        db_session.flush()
        source_entry = OnlineQueueEntry(
            queue_id=source_today.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Surface Patient R9",
            status="waiting",
            source="desk",
        )
        db_session.add(source_entry)
        # round 10: сид-данные коммитятся — отказ (409) откатывает сессию,
        # и объекты должны пережить этот rollback
        db_session.commit()

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=test_doctor.id,
                    target_date=today,
                    daily_queue_id=source_today.id,
                    entry_ids=None,
                    expected_entry_ids=[source_entry.id],
                    reason="лаборатория недоступна",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        # 3808 review round 10 (P2 HTTP contract): доменный отказ —
        # 409 с объяснением, а не необработанная серверная ошибка
        assert exc_info.value.status_code == 409
        # round 11 (P2 409 disambiguation): код класса отказа — клиент
        # отличает этот 409 от дрейфа состава предпросмотра
        assert exc_info.value.code == "force_majeure_domain_refusal"
        assert "владельца назначения" in exc_info.value.detail
        assert "Операция отклонена" in exc_info.value.detail
        assert f"id={doctor_queue_tomorrow.id}" in exc_info.value.detail
        # fail closed: запись-источник не отменена и не перенесена
        db_session.refresh(source_entry)
        assert source_entry.status == "waiting"
        assert source_entry.queue_id == source_today.id
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .count()
            == 0
        )
        # врачебная очередь завтра не получила пациентов
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == doctor_queue_tomorrow.id)
            .count()
            == 0
        )
        # и никакой новой очереди на завтра не создано
        assert (
            db_session.query(DailyQueue).filter(DailyQueue.day == tomorrow).count()
            == 1
        )

    def test_transfer_resource_owned_source_rejects_foreign_resource_same_tag_destination(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 9 (P1 destination owner recheck), зеркальный
        случай: тег источника ПЕРЕВЯЗАН в реестре на другой ресурс
        (queue_tag глобально уникален — старый ряд сменил тег, новый
        принял его). Поверхность (day, tag) завтра будет создана из
        ЧУЖОГО ресурса — перенос отказом, а не тихий переезд; новых
        очередей при отказе не создаётся (fail closed без записей)."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        # ресурс-владелец источника; после создания его тег перевязан
        resource_b = QueueResource(
            code="lab_surface_r9b",
            queue_tag="lab_orphan_r9",
            display_name="Лаборатория B",
            active=True,
        )
        db_session.add(resource_b)
        db_session.flush()
        source_today = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource_b.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        db_session.add(source_today)
        db_session.flush()
        # тег specialty теперь ведёт к ДРУГОМУ активному ресурсу
        resource_a = QueueResource(
            code="lab_surface_r9a",
            queue_tag=test_doctor.specialty,
            display_name="Лаборатория A",
            active=True,
        )
        db_session.add(resource_a)
        db_session.flush()
        source_entry = OnlineQueueEntry(
            queue_id=source_today.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Surface Patient R9b",
            status="waiting",
            source="desk",
        )
        db_session.add(source_entry)
        # round 10: сид-данные коммитятся — отказ (409) откатывает сессию,
        # и объекты должны пережить этот rollback
        db_session.commit()

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=test_doctor.id,
                    target_date=today,
                    daily_queue_id=source_today.id,
                    entry_ids=None,
                    expected_entry_ids=[source_entry.id],
                    reason="лаборатория B недоступна",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        # 3808 review round 10 (P2 HTTP contract): 409, не HTTP 500
        assert exc_info.value.status_code == 409
        # round 11 (P2 409 disambiguation): код класса отказа
        assert exc_info.value.code == "force_majeure_domain_refusal"
        assert "владельца назначения" in exc_info.value.detail
        # отказ объясняет перевязку тега
        assert f"id={resource_a.id}" in exc_info.value.detail
        # fail closed БЕЗ записей: источник не тронут
        db_session.refresh(source_entry)
        assert source_entry.status == "waiting"
        assert source_entry.queue_id == source_today.id
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .count()
            == 0
        )
        # никакой очереди на завтра не создано (даже пустой)
        assert (
            db_session.query(DailyQueue).filter(DailyQueue.day == tomorrow).count()
            == 0
        )

    def test_domain_service_owner_conflict_raises_force_majeure_error(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 10 (P2 HTTP contract), пин нижнего слоя:
        доменный сервис отказывает именно ForceMajeureError — API-слой
        отвечает за перевод в 409, но исходный контракт отказа остаётся
        доменным (не HTTP-типом)."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        resource = QueueResource(
            code="lab_surface_r10",
            queue_tag=test_doctor.specialty,
            display_name="Лаборатория (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        source_today = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue_tomorrow = DailyQueue(
            day=tomorrow,
            specialist_id=test_doctor.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        db_session.add_all([source_today, doctor_queue_tomorrow])
        db_session.flush()
        source_entry = OnlineQueueEntry(
            queue_id=source_today.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Surface Patient R10",
            status="waiting",
            source="desk",
        )
        db_session.add(source_entry)
        db_session.commit()

        service = ForceMajeureService(db_session)
        entries = service.get_pending_entries(
            queue_id=source_today.id, target_date=today
        )
        with pytest.raises(ForceMajeureError):
            service.transfer_entries_to_tomorrow(
                entries=entries,
                specialist_id=test_doctor.id,
                reason="лаборатория недоступна",
                performed_by_id=1,
                send_notifications=False,
                source_date=today,
                source_queue=source_today,
            )

    def test_two_queue_repeated_bank_refund_counts_only_new_requests(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 review round 7 (P2): a visit with pending entries in two
        queues — the second bank-transfer cancel is an idempotent replay:
        zero new RefundRequest rows, and the response reports
        refund_requests_created == 0 (the repeat is exposed separately as
        refund_requests_existing == 1)."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        from app.models.refund_deposit import RefundRequest

        today = date.today()
        queue_a = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="two_queue_a_r7",
            active=True,
        )
        queue_b = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="two_queue_b_r7",
            active=True,
        )
        db_session.add_all([queue_a, queue_b])
        db_session.flush()
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("300.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry_a = OnlineQueueEntry(
            queue_id=queue_a.id,
            visit_id=visit.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Two Queue Patient A",
            status="waiting",
            source="desk",
        )
        entry_b = OnlineQueueEntry(
            queue_id=queue_b.id,
            visit_id=visit.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Two Queue Patient B",
            status="waiting",
            source="desk",
        )
        db_session.add_all([payment, entry_a, entry_b])
        db_session.commit()

        service = ForceMajeureService(db_session)

        first = service.cancel_entries_with_refund(
            entries=[entry_a],
            reason="Doctor emergency queue A",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        assert first["refund_requests_created"] == 1
        assert first["refund_requests_existing"] == 0

        second = service.cancel_entries_with_refund(
            entries=[entry_b],
            reason="Doctor emergency queue B",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert second["cancelled"] == 1
        # the replay created ZERO new bank requests — and says so
        assert second["refund_requests_created"] == 0
        assert second["refund_requests_existing"] == 1
        refund_info = second["details"][0]["refund_info"]
        assert refund_info["already_refunded"] is True
        # exactly one RefundRequest row exists for the payment in total
        assert (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .count()
            == 1
        )

    def test_cancel_with_refund_selects_only_the_bound_queue_entries(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        resource = QueueResource(
            code="cardio_surface_c",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        surface_queue = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_own_queue_c",
            active=True,
        )
        db_session.add_all([surface_queue, doctor_queue])
        db_session.flush()

        own_entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Own Queue Patient",
            status="waiting",
            source="desk",
        )
        surface_entry = OnlineQueueEntry(
            queue_id=surface_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Surface Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([own_entry, surface_entry])
        db_session.flush()

        captured = {}
        real_service = get_force_majeure_service(db_session)

        def fake_cancel(**kwargs):
            captured["entries"] = kwargs["entries"]
            return {"success": True, "cancelled": len(kwargs["entries"])}

        monkeypatch.setattr(real_service, "cancel_entries_with_refund", fake_cancel)
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: real_service,
        )

        result = ForceMajeureApiService(db_session).cancel_queue_with_refund(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=doctor_queue.id,
                entry_ids=None,
                expected_entry_ids=[own_entry.id],
                reason="doctor emergency",
                refund_type="deposit",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["cancelled"] == 1
        assert [entry.id for entry in captured["entries"]] == [own_entry.id]

    def test_cancel_with_refund_rejects_entry_linked_to_other_patient_visit(
        self,
        db_session,
        test_doctor,
        test_patient,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )

        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998900000113",
        )
        db_session.add_all([queue, other_patient])
        db_session.flush()

        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.utcnow(),
        )
        db_session.add(other_visit)
        db_session.flush()

        payment = Payment(
            visit_id=other_visit.id,
            amount=Decimal("120.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=other_visit.id,
            source="online",
            status="waiting",
        )
        db_session.add_all([payment, entry])
        db_session.commit()
        db_session.refresh(entry)
        db_session.refresh(other_visit)

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["cancelled"] == 0
        assert result["failed"] == 1
        assert "does not belong" in result["errors"][0]["error"]

        db_session.refresh(entry)
        db_session.refresh(other_visit)
        assert entry.status == "waiting"
        assert other_visit.status == "open"
        assert (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .count()
            == 0
        )
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 0
        )

    def test_cancel_queue_with_refund_rejects_invalid_type(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: SimpleNamespace(),
        )

        repository = SimpleNamespace(db=None)
        service = ForceMajeureApiService(db=None, repository=repository)

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    refund_type="bad",
                    entry_ids=None,
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=None,
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=10,
            )

        assert exc_info.value.status_code == 400

    def test_process_refund_request_reject_requires_reason(self):
        request_obj = SimpleNamespace(
            status="pending",
            processed_by=None,
            processed_at=None,
            patient=None,
            processor=None,
            id=1,
            patient_id=2,
            payment_id=3,
            original_amount=Decimal("10"),
            refund_amount=Decimal("10"),
            commission_amount=Decimal("0"),
            refund_type="deposit",
            reason="r",
            is_automatic=False,
            bank_card_number=None,
            created_at=None,
        )

        class Repository:
            def get_refund_request(self, request_id):
                return request_obj

            # 3808 round 6: process_refund_request читает заявку только
            # через заблокированный (FOR UPDATE) путь
            def get_refund_request_for_update(self, request_id):
                return request_obj

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.process_refund_request(
                request_id=1,
                process_request=SimpleNamespace(
                    action="reject",
                    rejection_reason=None,
                    bank_card_number=None,
                    manager_notes=None,
                ),
                current_user=SimpleNamespace(id=1, full_name="Admin"),
            )
        assert exc_info.value.status_code == 400

    def test_refund_request_serialization_exposes_backend_owned_actions(self):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace())

        def make_request(status):
            return SimpleNamespace(
                status=status,
                processed_by=None,
                processed_at=None,
                patient=None,
                processor=None,
                id=1,
                patient_id=2,
                payment_id=3,
                original_amount=Decimal("10"),
                refund_amount=Decimal("10"),
                commission_amount=Decimal("0"),
                refund_type="deposit",
                reason="r",
                is_automatic=False,
                bank_card_number=None,
                created_at=None,
            )

        pending = service._serialize_refund_request(make_request("pending"))
        approved = service._serialize_refund_request(make_request("approved"))
        rejected = service._serialize_refund_request(make_request("rejected"))

        assert pending["available_actions"] == ["approve", "reject"]
        assert pending["can_approve"] is True
        assert pending["can_reject"] is True
        assert pending["can_complete"] is False

        assert approved["available_actions"] == ["reject", "complete"]
        assert approved["can_approve"] is False
        assert approved["can_reject"] is True
        assert approved["can_complete"] is True

        assert rejected["available_actions"] == []
        assert rejected["can_approve"] is False
        assert rejected["can_reject"] is False
        assert rejected["can_complete"] is False

    def test_use_deposit_for_payment_checks_balance(self):
        deposit = SimpleNamespace(
            balance=Decimal("50"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )

        class Repository:
            def get_patient_deposit_for_update(self, *, patient_id):
                return deposit

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.use_deposit_for_payment(
                request=SimpleNamespace(
                    patient_id=2,
                    amount=100,
                    visit_id=None,
                    description=None,
                ),
                current_user_id=1,
            )
        assert exc_info.value.status_code == 400

    def test_use_deposit_for_payment_rejects_cross_patient_visit(self):
        deposit = SimpleNamespace(
            balance=Decimal("100"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )
        state = {"flushed": False}

        class Repository:
            def get_patient_deposit_for_update(self, *, patient_id):
                return deposit

            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id, patient_id=99)

            def flush(self):
                state["flushed"] = True

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.use_deposit_for_payment(
                request=SimpleNamespace(
                    patient_id=2,
                    amount=40,
                    visit_id=9,
                    description=None,
                ),
                current_user_id=1,
            )

        assert exc_info.value.status_code == 400
        assert deposit.balance == Decimal("100")
        assert state["flushed"] is False

    # -- 3808 review round 13 (residual P1): единый механизм конкурентно-
    # безопасного изменения депозита — ручные операции ходят через
    # заблокированную строку (см. repository.get_*_for_update) --

    def test_use_deposit_for_payment_debits_the_locked_row(self):
        """Успешное списание: строка взята через
        get_patient_deposit_for_update (единый механизм с форс-мажорной
        ногой _add_to_deposit), баланс и balance_after сходятся."""
        deposit = SimpleNamespace(
            balance=Decimal("100"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )
        state = {"flushed": 0, "added": []}

        class Repository:
            def get_patient_deposit_for_update(self, *, patient_id):
                state["locked_patient_id"] = patient_id
                return deposit

            def flush(self):
                state["flushed"] += 1

            def add(self, obj):
                state["added"].append(obj)

            def commit(self):
                state["committed"] = True

            def refresh(self, obj):
                state["refreshed"] = obj

        service = ForceMajeureApiService(db=None, repository=Repository())
        payload = service.use_deposit_for_payment(
            request=SimpleNamespace(
                patient_id=2,
                amount=40,
                visit_id=None,
                description=None,
            ),
            current_user_id=7,
        )

        assert state["locked_patient_id"] == 2
        assert deposit.balance == Decimal("60")
        assert payload["balance"] == 60.0
        [debit] = state["added"]
        assert debit.transaction_type == "debit"
        assert debit.amount == Decimal("40")
        assert debit.balance_after == Decimal("60")
        assert debit.performed_by == 7
        assert state["committed"] is True
        assert state["refreshed"] is deposit

    def test_add_to_deposit_sums_into_locked_existing_row(self):
        """Пополнение существующего депозита: get_or_create... возвращает
        created=False — сумма прибавляется к заблокированной строке."""
        deposit = SimpleNamespace(
            balance=Decimal("100"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )
        state = {"added": []}

        class Repository:
            def get_or_create_patient_deposit_for_update(
                self, *, patient_id, initial_balance
            ):
                state["locked_patient_id"] = patient_id
                state["initial_balance"] = initial_balance
                return deposit, False

            def flush(self):
                pass

            def add(self, obj):
                state["added"].append(obj)

            def commit(self):
                pass

            def refresh(self, obj):
                pass

        service = ForceMajeureApiService(db=None, repository=Repository())
        payload = service.add_to_deposit(
            request=SimpleNamespace(
                patient_id=2,
                amount=30,
                description=None,
            ),
            current_user_id=5,
        )

        assert state["locked_patient_id"] == 2
        assert deposit.balance == Decimal("130")
        assert payload["balance"] == 130.0
        [credit] = state["added"]
        assert credit.transaction_type == "credit"
        assert credit.amount == Decimal("30")
        assert credit.balance_after == Decimal("130")

    def test_add_to_deposit_uses_initial_balance_for_created_row(self):
        """Создание депозита через конкурентно безопасную ветку: created=True
        — строка уже создана с initial_balance, двойное прибавление
        недопустимо (balance = amount, НЕ amount + amount)."""
        deposit = SimpleNamespace(
            balance=Decimal("30"),
            is_active=True,
            patient=None,
            id=9,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )
        state = {"added": []}

        class Repository:
            def get_or_create_patient_deposit_for_update(
                self, *, patient_id, initial_balance
            ):
                state["initial_balance"] = initial_balance
                return deposit, True

            def flush(self):
                pass

            def add(self, obj):
                state["added"].append(obj)

            def commit(self):
                pass

            def refresh(self, obj):
                pass

        service = ForceMajeureApiService(db=None, repository=Repository())
        payload = service.add_to_deposit(
            request=SimpleNamespace(
                patient_id=2,
                amount=30,
                description=None,
            ),
            current_user_id=5,
        )

        # initial_balance = amount, и НИКАКОГО повторного += поверх
        assert state["initial_balance"] == Decimal("30")
        assert deposit.balance == Decimal("30"), "двойное зачисление!"
        assert payload["balance"] == 30.0
        [credit] = state["added"]
        assert credit.balance_after == Decimal("30")

    # -- Review round 3 (#3809 P1/P2): preview set binding + serialization --

    def test_transfer_daily_queue_id_requires_expected_entry_ids(self):
        """Round 3 P1: a bound mutation without the preview snapshot is
        refused — it would re-select the whole live queue and could touch
        patients the registrar never saw in the preview."""
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=7,
                    target_date=date.today(),
                    daily_queue_id=5,
                    entry_ids=None,
                    expected_entry_ids=None,
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert exc_info.value.status_code == 422
        assert "expected_entry_ids" in exc_info.value.detail

    def test_cancel_daily_queue_id_requires_expected_entry_ids(self):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    specialist_id=7,
                    target_date=date.today(),
                    daily_queue_id=5,
                    entry_ids=None,
                    expected_entry_ids=[],
                    reason="reason",
                    refund_type="deposit",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        # an EMPTY snapshot is a missing preview, not an empty-queue operation
        assert exc_info.value.status_code == 422
        assert "expected_entry_ids" in exc_info.value.detail

    def test_expected_entry_ids_only_pairs_with_daily_queue_id(self):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        with pytest.raises(ForceMajeureApiDomainError) as no_queue:
            service.transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=7,
                    target_date=None,
                    daily_queue_id=None,
                    entry_ids=None,
                    expected_entry_ids=[11],
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert no_queue.value.status_code == 422
        assert "daily_queue_id" in no_queue.value.detail

        with pytest.raises(ForceMajeureApiDomainError) as with_entry_ids:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    specialist_id=7,
                    target_date=None,
                    daily_queue_id=None,
                    entry_ids=[11],
                    expected_entry_ids=[12],
                    reason="reason",
                    refund_type="deposit",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert with_entry_ids.value.status_code == 422
        assert "взаимоисключающие" in with_entry_ids.value.detail

    def test_transfer_rejects_patient_added_after_preview(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """The registrar previewed one patient; a second patient joined the
        queue afterwards. The bound POST refuses with 409 and moves NOBODY:
        the unpreviewed patient cannot be transferred silently."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_preview_drift_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        previewed = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Previewed Patient",
            status="waiting",
            source="desk",
        )
        late_joiner = OnlineQueueEntry(
            queue_id=queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Late Joiner",
            status="waiting",
            source="desk",
        )
        db_session.add_all([previewed, late_joiner])
        db_session.flush()

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=test_doctor.id,
                    target_date=today,
                    daily_queue_id=queue.id,
                    entry_ids=None,
                    expected_entry_ids=[previewed.id],
                    reason="doctor emergency",
                    send_notifications=False,
                ),
                current_user_id=1,
            )

        assert exc_info.value.status_code == 409
        # round 11 (P2 409 disambiguation): дрейф состава помечен своим
        # кодом — клиент не спутает его с конфликтом владельцев
        assert exc_info.value.code == "force_majeure_preview_drift"
        assert "добавилось: 1" in exc_info.value.detail
        assert "исчезло: 0" in exc_info.value.detail

        # Refusal is total: no entry moved, no entry cancelled.
        db_session.refresh(previewed)
        db_session.refresh(late_joiner)
        assert previewed.status == "waiting"
        assert late_joiner.status == "waiting"
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .count()
            == 0
        )

    def test_cancel_rejects_entry_removed_after_preview(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """The registrar previewed two patients; one was served by a
        concurrent writer before the confirmation. The bound POST refuses
        with 409: no cancellation and no refund money movement."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_cancel_drift_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("150.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        staying = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Staying Patient",
            status="waiting",
            source="desk",
        )
        served = OnlineQueueEntry(
            queue_id=queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Served Patient",
            # The concurrent writer already processed this entry between
            # the preview and the confirmation: at POST time it is NOT in
            # the live pending set anymore → drift vs the snapshot.
            status="served",
            source="desk",
        )
        db_session.add_all([payment, staying, served])
        db_session.flush()
        staying.visit_id = visit.id
        db_session.flush()

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            ForceMajeureApiService(db_session).cancel_queue_with_refund(
                request=SimpleNamespace(
                    specialist_id=test_doctor.id,
                    target_date=today,
                    daily_queue_id=queue.id,
                    entry_ids=None,
                    expected_entry_ids=[staying.id, served.id],
                    reason="doctor emergency",
                    refund_type="deposit",
                    send_notifications=False,
                ),
                current_user_id=1,
            )

        assert exc_info.value.status_code == 409
        # round 11 (P2 409 disambiguation): дрейф состава помечен своим кодом
        assert exc_info.value.code == "force_majeure_preview_drift"
        assert "добавилось: 0" in exc_info.value.detail

        # Refusal is total: the remaining entry is intact and no money moved.
        db_session.refresh(staying)
        assert staying.status == "waiting"
        assert (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .count()
            == 0
        )
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 0
        )

    def test_bound_mutation_takes_queue_row_lock(self):
        """Characterization pin (the repo's established source-assertion
        idiom): the bound path locks the queue row FOR UPDATE before the
        entry set is read, and re-reads past the identity map. The lock
        lives in the repository (session-calls boundary for services)."""
        import inspect

        from app.repositories.force_majeure_api_repository import (
            ForceMajeureApiRepository,
        )

        repository_source = inspect.getsource(
            ForceMajeureApiRepository.get_daily_queue_for_update
        )
        assert "with_for_update" in repository_source
        assert "populate_existing" in repository_source

        service_source = inspect.getsource(
            ForceMajeureApiService._validated_daily_queue
        )
        assert "get_daily_queue_for_update" in service_source

        bound_source = inspect.getsource(
            ForceMajeureApiService._bound_pending_entries
        )
        assert "409" in bound_source

    def test_cancel_skips_entry_processed_after_selection(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """Domain re-check: an entry whose status was changed by a
        concurrent writer after selection is skipped, not cancelled and
        not refunded a second time."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_skip_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Already Processed",
            status="served",
            source="desk",
        )
        db_session.add(entry)
        db_session.commit()

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["cancelled"] == 0
        assert result["skipped"] == 1
        assert result["failed"] == 0
        db_session.refresh(entry)
        assert entry.status == "served"
        assert (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .count()
            == 0
        )

    def test_transfer_skips_entry_processed_after_selection(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_skip_transfer_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Already Cancelled",
            status="cancelled",
            source="desk",
        )
        db_session.add(entry)
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[entry],
            specialist_id=test_doctor.id,
            reason="Doctor emergency",
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["transferred"] == 0
        assert result["skipped"] == 1
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .count()
            == 0
        )

    def test_deposit_refund_is_idempotent_per_payment(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """A previous force-majeure leg already credited this payment to
        the deposit: a replay does not create a second credit row and
        does not change the balance."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_idem_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("200.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            visit_id=visit.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Idempotent Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([payment, entry])
        db_session.flush()

        # The PREVIOUS force-majeure leg: credit already exists.
        deposit = PatientDeposit(
            patient_id=test_patient.id, balance=Decimal("200.00")
        )
        db_session.add(deposit)
        db_session.flush()
        previous_credit = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type="credit",
            amount=Decimal("200.00"),
            balance_after=Decimal("200.00"),
            description="Возврат (форс-мажор): earlier leg",
            payment_id=payment.id,
        )
        db_session.add(previous_credit)
        db_session.commit()

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency replay",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["cancelled"] == 1
        refund_info = result["details"][0]["refund_info"]
        assert refund_info["already_refunded"] is True

        db_session.refresh(deposit)
        assert deposit.balance == Decimal("200.00")
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 1
        )

    def test_refund_request_is_idempotent_per_payment(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """bank_transfer leg: an existing automatic request for the same
        payment is returned instead of a duplicate."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        from app.models.refund_deposit import RefundRequest

        today = date.today()
        queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_idem_request_queue",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("300.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            visit_id=visit.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Idempotent Request Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([payment, entry])
        db_session.flush()

        existing_request = RefundRequest(
            patient_id=test_patient.id,
            payment_id=payment.id,
            original_amount=Decimal("300.00"),
            refund_amount=Decimal("300.00"),
            commission_amount=Decimal("0"),
            refund_type="bank_transfer",
            status="pending",
            reason="earlier leg",
            is_automatic=True,
        )
        db_session.add(existing_request)
        db_session.commit()

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency replay",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["cancelled"] == 1
        refund_info = result["details"][0]["refund_info"]
        assert refund_info["already_refunded"] is True
        assert refund_info["request_id"] == existing_request.id

        assert (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .count()
            == 1
        )

    def test_deposit_credit_partial_unique_rejects_duplicate(
        self, db_session, test_doctor, test_patient
    ):
        """Model-level backstop: two credit rows for the same payment are
        impossible regardless of what any code path does (0087 index)."""
        from sqlalchemy.exc import IntegrityError

        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("120.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        deposit = PatientDeposit(
            patient_id=test_patient.id, balance=Decimal("0")
        )
        db_session.add_all([payment, deposit])
        db_session.flush()

        first = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type="credit",
            amount=Decimal("120.00"),
            balance_after=Decimal("120.00"),
            description="first refund leg",
            payment_id=payment.id,
        )
        db_session.add(first)
        db_session.flush()

        duplicate = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type="credit",
            amount=Decimal("120.00"),
            balance_after=Decimal("240.00"),
            description="double refund leg",
            payment_id=payment.id,
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_refund_request_auto_partial_unique_rejects_duplicate(
        self, db_session, test_doctor, test_patient
    ):
        """Automatic (force majeure) refund requests are unique per
        payment; the manual cashier leg stays unconstrained."""
        from sqlalchemy.exc import IntegrityError

        from app.models.refund_deposit import RefundRequest

        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("90.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.flush()

        automatic = RefundRequest(
            patient_id=test_patient.id,
            payment_id=payment.id,
            original_amount=Decimal("90.00"),
            refund_amount=Decimal("90.00"),
            commission_amount=Decimal("0"),
            refund_type="bank_transfer",
            status="pending",
            reason="automatic leg",
            is_automatic=True,
        )
        manual = RefundRequest(
            patient_id=test_patient.id,
            payment_id=payment.id,
            original_amount=Decimal("90.00"),
            refund_amount=Decimal("90.00"),
            commission_amount=Decimal("0"),
            refund_type="cash",
            status="pending",
            reason="manual cashier leg",
            is_automatic=False,
        )
        db_session.add_all([automatic, manual])
        db_session.flush()  # manual + automatic coexist legally

        duplicate_automatic = RefundRequest(
            patient_id=test_patient.id,
            payment_id=payment.id,
            original_amount=Decimal("90.00"),
            refund_amount=Decimal("90.00"),
            commission_amount=Decimal("0"),
            refund_type="bank_transfer",
            status="pending",
            reason="double automatic leg",
            is_automatic=True,
        )
        db_session.add(duplicate_automatic)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def _seed_shared_payment_two_queues(
        self, db_session, test_doctor, test_patient, *, queue_tag
    ):
        """3808 round 4 (P1 cross-channel): ОДИН оплаченный визит в записях
        ДВУХ очередей — патологический дубликат-референс, на котором два
        независимых канала 0087 давали двойной возврат."""
        today = date.today()
        queues = []
        for suffix in ("a", "b"):
            queue = DailyQueue(
                day=today,
                specialist_id=test_doctor.id,
                queue_tag=f"{queue_tag}_{suffix}",
                active=True,
            )
            db_session.add(queue)
            db_session.flush()
            queues.append(queue)

        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=today,
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()

        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("180.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.flush()

        entries = []
        for number, queue in enumerate(queues, start=1):
            entry = OnlineQueueEntry(
                queue_id=queue.id,
                visit_id=visit.id,
                number=number,
                patient_id=test_patient.id,
                patient_name="Cross Channel",
                status="waiting",
                source="desk",
            )
            db_session.add(entry)
            db_session.flush()
            entries.append(entry)

        db_session.commit()
        return payment, entries

    def test_cross_channel_deposit_then_bank_refunds_payment_once(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 round 4 (P1 cross-channel): deposit-нога первой очереди
        возвращает платёж на депозит; bank-нога ВТОРОЙ очереди с тем же
        визитом обязана увидеть возврат ЧЕРЕЗ канал и не создавать вторую
        автоматическую заявку — единая защита по payment_id (0088), а не
        два независимых частичных индекса 0087."""
        from app.models.refund_deposit import PaymentRefundClaim, RefundRequest

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        payment, entries = self._seed_shared_payment_two_queues(
            db_session, test_doctor, test_patient, queue_tag="fm_x_dep_bank"
        )

        first = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[0]],
            reason="Doctor emergency",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        assert not first["details"][0]["refund_info"].get("already_refunded")

        second = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[1]],
            reason="Doctor emergency",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert second["cancelled"] == 1
        refund_info = second["details"][0]["refund_info"]
        assert refund_info["already_refunded"] is True
        assert refund_info["prior_channel"] == "deposit"

        assert (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .count()
            == 0
        ), "банковская нога не создаётся поверх депозитной"
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 1
        )
        claims = (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .all()
        )
        assert len(claims) == 1, claims
        assert claims[0].channel == "deposit"
        assert claims[0].deposit_transaction_id is not None

    def test_cross_channel_bank_then_deposit_refunds_payment_once(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 round 4 (P1 cross-channel), обратный порядок: автоматическая
        банковская заявка первой очереди занимает возврат; deposit-нога
        второй очереди не двигает баланс и не создаёт кредит."""
        from app.models.refund_deposit import PaymentRefundClaim, RefundRequest

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        payment, entries = self._seed_shared_payment_two_queues(
            db_session, test_doctor, test_patient, queue_tag="fm_x_bank_dep"
        )

        first = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[0]],
            reason="Doctor emergency",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        assert not first["details"][0]["refund_info"].get("already_refunded")

        second = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[1]],
            reason="Doctor emergency",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )
        assert second["cancelled"] == 1
        refund_info = second["details"][0]["refund_info"]
        assert refund_info["already_refunded"] is True
        assert refund_info["prior_channel"] == "refund_request"

        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 0
        ), "депозитный кредит не создаётся поверх банковской заявки"
        assert (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .count()
            == 0
        ), "баланс пациента не трогался"
        assert (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .count()
            == 1
        )
        claims = (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .all()
        )
        assert len(claims) == 1, claims
        assert claims[0].channel == "refund_request"
        assert claims[0].refund_request_id is not None

    def test_payment_refund_claim_unique_rejects_duplicate(
        self, db_session, test_doctor, test_patient
    ):
        """Модельный бэкстоп ЕДИНОГО guard-а: второй claim по тому же
        payment_id невозможен, что бы ни делал код (миграция 0088)."""
        from sqlalchemy.exc import IntegrityError

        from app.models.refund_deposit import PaymentRefundClaim

        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("140.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.flush()

        first = PaymentRefundClaim(
            payment_id=payment.id,
            channel="deposit",
            reason="unified guard probe",
        )
        db_session.add(first)
        db_session.flush()

        duplicate = PaymentRefundClaim(
            payment_id=payment.id,
            channel="refund_request",
            reason="must never persist",
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_cancel_deadlock_maps_to_409(self, monkeypatch):
        """3808 round 4: единый refund-claim сериализует возвраты одного
        платежа между очередями; на патологическом порядке обработки
        PostgreSQL сам разрешает взаимоблокировку (40P01; сюда же —
        failure сериализации 40001). Эта ситуация переводится в 409 с
        подсказкой повторить, а не в 500: инвариант «один возврат на
        платеж» не нарушен, повтор получит already_refunded."""
        from sqlalchemy.exc import OperationalError

        orig = Exception("deadlock detected")
        orig.pgcode = "40P01"
        deadlock = OperationalError(
            "INSERT INTO payment_refund_claims ...", {}, orig
        )

        def raise_deadlock(**kwargs):
            raise deadlock

        force_service = SimpleNamespace(
            cancel_entries_with_refund=raise_deadlock
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: force_service,
        )

        repository = SimpleNamespace(
            db=None,
            list_pending_entries_by_ids=lambda *args, **kwargs: [
                SimpleNamespace(id=5)
            ],
        )
        service = ForceMajeureApiService(db=None, repository=repository)

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    refund_type="deposit",
                    entry_ids=[5],
                    specialist_id=1,
                    target_date=date.today(),
                    daily_queue_id=None,
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=10,
            )

        assert exc_info.value.status_code == 409
        # round 11 (P2 409 disambiguation): гонка возвратов — свой код,
        # не force_majeure_preview_drift
        assert exc_info.value.code == "force_majeure_concurrent_refund"

    def _seed_refund_lifecycle_world(self, db_session, test_doctor, test_patient):
        """3808 round 5 (P1 claim lifecycle): мир раунда-4 «один платёж в
        записях ДВУХ очередей» + КАССИР (processed_by FK): первая нога
        отменяет запись очереди A, повторный возврат идёт через запись
        очереди B (запись A к тому моменту уже cancelled)."""
        from app.models.user import User

        cashier = User(
            username="fm_lifecycle_cashier",
            full_name="FM Lifecycle Cashier",
            email="fm-lifecycle-cashier@test.local",
            hashed_password="not-a-real-hash",
            role="admin",
            is_active=True,
        )
        db_session.add(cashier)
        db_session.flush()
        db_session.commit()

        payment, entries = self._seed_shared_payment_two_queues(
            db_session, test_doctor, test_patient, queue_tag="fm_lifecycle"
        )
        return cashier, payment, entries

    def _reject_request(self, db_session, request_id, cashier):
        """Кассир отклоняет заявку через реальный API-сервис (тот же путь,
        что и продакшн- эндпоинт)."""
        service = ForceMajeureApiService(db=db_session)
        return service.process_refund_request(
            request_id=request_id,
            process_request=SimpleNamespace(
                action="reject",
                rejection_reason="invalid bank details",
                bank_card_number=None,
                manager_notes=None,
            ),
            current_user=SimpleNamespace(id=cashier.id, full_name=cashier.full_name),
        )

    def test_rejected_bank_request_releases_claim_and_allows_deposit_retry(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 round 5 (P1 claim lifecycle): pending -> rejected заявка
        денег не вернула — claim освобождается ТРАНЗАКЦИОННО с reject, и
        повторный возврат на депозит проходит (баланс пополнен, ровно один
        claim уже депозитного канала)."""
        from app.models.refund_deposit import (
            DepositTransaction,
            PatientDeposit,
            PaymentRefundClaim,
            RefundRequest,
        )

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        cashier, payment, entries = self._seed_refund_lifecycle_world(
            db_session, test_doctor, test_patient
        )

        first = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[0]],
            reason="Doctor emergency",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        request = (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .one()
        )
        assert request.status == "pending"
        assert (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .count()
            == 1
        )

        rejected = self._reject_request(db_session, request.id, cashier)
        assert rejected["status"] == "rejected"
        # claim освобождён в той же транзакции
        assert (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .count()
            == 0
        ), "reject обязан освободить claim платежа"

        # Повторный возврат на депозит: проходит без already_refunded
        second = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[1]],
            reason="Doctor emergency retry",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )
        assert second["cancelled"] == 1
        assert second["skipped"] == 0
        refund_info = second["details"][0]["refund_info"]
        assert not refund_info.get("already_refunded"), second

        deposit = (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .one()
        )
        assert deposit.balance == payment.amount
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 1
        )
        claims = (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .all()
        )
        assert len(claims) == 1
        assert claims[0].channel == "deposit"
        assert claims[0].deposit_transaction_id is not None
        # историческая заявка осталась rejected, денег по ней не уходило
        db_session.refresh(request)
        assert request.status == "rejected"

    def test_rejected_bank_request_allows_corrected_bank_retry(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 round 5 (P1 claim lifecycle), тот же канал: после reject
        создаётся ВТОРАЯ автоматическая заявка (исправленные реквизиты) —
        статус-зависимый предикат 0087 это допускает; claim переходит к
        новой заявке."""
        from app.models.refund_deposit import PaymentRefundClaim, RefundRequest

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        cashier, payment, entries = self._seed_refund_lifecycle_world(
            db_session, test_doctor, test_patient
        )

        first = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[0]],
            reason="Doctor emergency",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        first_request = (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .one()
        )
        self._reject_request(db_session, first_request.id, cashier)

        second = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[1]],
            reason="Doctor emergency corrected details",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert second["cancelled"] == 1
        refund_info = second["details"][0]["refund_info"]
        assert not refund_info.get("already_refunded"), second

        requests = (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .order_by(RefundRequest.id)
            .all()
        )
        assert len(requests) == 2
        assert [r.status for r in requests] == ["rejected", "pending"]

        claims = (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .all()
        )
        assert len(claims) == 1
        assert claims[0].channel == "refund_request"
        assert claims[0].refund_request_id == requests[1].id

    def test_auto_request_unique_index_ignores_failed_statuses(
        self, db_session, test_doctor, test_patient
    ):
        """Предикат 0087 (round 5): терминальные не-платящие статусы
        покидают частичный уникальный индекс — rejected + cancelled +
        pending сосуществуют; ВТОРОЙ pending по-прежнему невозможен
        (живые статусы строго уникальны)."""
        from sqlalchemy.exc import IntegrityError

        from app.models.refund_deposit import RefundRequest

        visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        db_session.add(visit)
        db_session.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("130.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.flush()

        def _auto_request(status):
            return RefundRequest(
                patient_id=test_patient.id,
                payment_id=payment.id,
                original_amount=Decimal("130.00"),
                refund_amount=Decimal("130.00"),
                commission_amount=Decimal("0"),
                refund_type="bank_transfer",
                status=status,
                reason=f"probe {status}",
                is_automatic=True,
            )

        db_session.add(_auto_request("rejected"))
        db_session.add(_auto_request("cancelled"))
        db_session.add(_auto_request("pending"))
        db_session.flush()  # сосуществуют: уникальность только среди живых

        db_session.add(_auto_request("approved"))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_stale_claim_self_heals_on_next_refund(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """Ленивое самоисцеление (round 5): claim, привязанный к уже
        отклонённой заявке (симуляция строки до фикса или пути отклонения
        в обход process_refund_request), при следующем возврате
        распознаётся как мёртвый, освобождается и замещается живым."""
        from app.models.refund_deposit import PaymentRefundClaim, RefundRequest

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        cashier, payment, entries = self._seed_refund_lifecycle_world(
            db_session, test_doctor, test_patient
        )
        entry = entries[0]

        # «Старый мир»: заявка была, её отклонили БЕЗ освобождения claim
        dead_request = RefundRequest(
            patient_id=test_patient.id,
            payment_id=payment.id,
            original_amount=Decimal("160.00"),
            refund_amount=Decimal("160.00"),
            commission_amount=Decimal("0"),
            refund_type="bank_transfer",
            status="rejected",
            reason="legacy rejected leg",
            is_automatic=True,
        )
        db_session.add(dead_request)
        db_session.flush()
        stale_claim = PaymentRefundClaim(
            payment_id=payment.id,
            channel="refund_request",
            refund_request_id=dead_request.id,
            reason="stale claim left by a pre-fix path",
        )
        db_session.add(stale_claim)
        db_session.commit()

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency after stale claim",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["cancelled"] == 1
        refund_info = result["details"][0]["refund_info"]
        assert not refund_info.get("already_refunded"), result

        claims = (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .all()
        )
        assert len(claims) == 1
        assert claims[0].channel == "deposit"
        assert claims[0].deposit_transaction_id is not None
        # id-сравнение с stale_claim намеренно отсутствует: SQLite
        # переиспользует rowid после DELETE

    def test_process_refund_request_takes_row_lock_before_status_checks(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """3808 round 6 (P1 reject/complete race): process_refund_request
        читает заявку ТОЛЬКО через get_refund_request_for_update
        (SELECT ... FOR UPDATE до проверки статуса) — сериализация
        кассирских reject/complete на строке заявки. SQLite не
        воспроизводит FOR UPDATE-гонку, поэтому здесь проверяется сам
        путь чтения; поведенческое доказательство живёт в gate_d
        (test_cashier_reject_vs_complete_race_serializes_on_request_row)."""
        from app.models.refund_deposit import PaymentRefundClaim, RefundRequest

        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        cashier, payment, entries = self._seed_refund_lifecycle_world(
            db_session, test_doctor, test_patient
        )

        first = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entries[0]],
            reason="Doctor emergency",
            refund_type=RefundType.BANK_TRANSFER,
            performed_by_id=1,
            send_notifications=False,
        )
        assert first["cancelled"] == 1
        request = (
            db_session.query(RefundRequest)
            .filter(RefundRequest.payment_id == payment.id)
            .one()
        )
        assert request.status == "pending", request.status

        calls = {"for_update": 0, "plain": 0}
        locked_read = ForceMajeureApiRepository.get_refund_request_for_update
        plain_read = ForceMajeureApiRepository.get_refund_request

        def locked_spy(self, request_id):
            calls["for_update"] += 1
            return locked_read(self, request_id)

        def plain_spy(self, request_id):
            calls["plain"] += 1
            return plain_read(self, request_id)

        monkeypatch.setattr(
            ForceMajeureApiRepository, "get_refund_request_for_update", locked_spy
        )
        monkeypatch.setattr(ForceMajeureApiRepository, "get_refund_request", plain_spy)

        rejected = self._reject_request(db_session, request.id, cashier)
        assert rejected["status"] == "rejected", rejected

        assert calls["for_update"] == 1, calls
        assert calls["plain"] == 0, calls
        assert (
            db_session.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment.id)
            .count()
            == 0
        ), "reject по заблокированной строке всё так же освобождает claim"
