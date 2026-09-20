"""PostgreSQL proofs for atomic lab draft writers.

The parent ``lab_report_instances`` row is the aggregate lock. Two sessions
that start from the same version must serialize there; the waiter must reload
the row after the winner commits and reject its stale token. Finalization uses
the same lock so a delayed draft save cannot mutate an immutable report.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.lab import (
    LabReportFieldDef,
    LabReportInstance,
    LabReportSection,
    LabReportTemplate,
    LabReportTemplateVersion,
)
from app.models.patient import Patient
from app.repositories.lab_reporting_api_repository import LabReportingApiRepository
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def lab_lock_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("lab draft concurrency proof requires DATABASE_URL for PostgreSQL")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("lab draft concurrency proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_lab_draft_lock_" + uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
    except Exception as exc:  # noqa: BLE001 - environmental skip, not product logic
        admin.dispose()
        pytest.skip(f"disposable PostgreSQL unavailable: {exc}")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=10000"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def lab_instance_version(lab_lock_engine):
    with Session(lab_lock_engine) as session:
        patient = Patient(
            last_name="SYNTHETIC-Lock",
            first_name="SYNTHETIC-Lab",
        )
        template = LabReportTemplate(
            code=f"synth_lock_{uuid4().hex[:8]}",
            name="SYNTHETIC lock proof",
            family="synthetic",
        )
        version = LabReportTemplateVersion(
            template=template,
            version_no=1,
            status="DRAFT",
            layout_preset="standard",
            page_settings={},
            branding_overrides={},
            signer_defaults={},
        )
        section = LabReportSection(
            template_version=version,
            key="main",
            title="SYNTHETIC",
            section_style={},
        )
        section.fields.append(
            LabReportFieldDef(
                field_key="wbc",
                label="SYNTHETIC WBC",
                value_type="text",
                reference_mode="static_text",
                required=False,
            )
        )
        session.add(patient)
        session.flush()
        instance = LabReportInstance(
            patient_id=patient.id,
            template=template,
            template_version=version,
            status="DRAFT",
            patient_snapshot={},
            branding_snapshot={},
            signer_snapshot={},
            updated_at=datetime(2026, 9, 20, 9, 30, 0, 123456, tzinfo=UTC),
        )
        session.add(instance)
        session.commit()
        return instance.id, instance.updated_at


def _wait_for_blocker(engine, pid: int, finished: threading.Event) -> bool:
    deadline = time.monotonic() + 5
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            if connection.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
            ):
                return True
            if finished.wait(0.01):
                return False
    return False


class _PausingLockRepository(LabReportingApiRepository):
    def __init__(self, db: Session, locked: threading.Event, release: threading.Event):
        super().__init__(db)
        self._locked = locked
        self._release = release

    def get_instance_for_update(self, instance_id: int):  # type: ignore[no-untyped-def]
        instance = super().get_instance_for_update(instance_id)
        self._locked.set()
        if not self._release.wait(8):
            raise AssertionError("lab aggregate lock holder was not released")
        return instance


def test_same_version_concurrent_saves_allow_one_writer(
    lab_lock_engine,
    lab_instance_version,
):
    instance_id, original = lab_instance_version
    locked = threading.Event()
    release = threading.Event()
    second_ready = threading.Event()
    second_finished = threading.Event()
    result: dict[str, object] = {}

    def first_save() -> None:
        try:
            with Session(lab_lock_engine) as session:
                repository = _PausingLockRepository(session, locked, release)
                instance, _ = LabReportingService(
                    session, repository=repository
                ).bulk_upsert_values(
                    instance_id,
                    [{"field_key": "wbc", "value_text": "5.2"}],
                    expected_updated_at=original.isoformat(),
                )
                result["first_status"] = instance.status
        except Exception as exc:  # noqa: BLE001 - surfaced in parent assertion
            result["first_error"] = repr(exc)

    def second_save() -> None:
        try:
            with Session(lab_lock_engine) as session:
                cached = session.get(LabReportInstance, instance_id)
                assert cached is not None and cached.updated_at == original
                result["second_pid"] = session.scalar(text("SELECT pg_backend_pid()"))
                second_ready.set()
                LabReportingService(session).bulk_upsert_values(
                    instance_id,
                    [{"field_key": "wbc", "value_text": "9.9"}],
                    expected_updated_at=original.isoformat(),
                )
                result["second_status"] = "accepted"
        except LabReportingDomainError as exc:
            result["second_conflict"] = exc.status_code
        except Exception as exc:  # noqa: BLE001 - surfaced in parent assertion
            result["second_error"] = repr(exc)
        finally:
            second_finished.set()

    first = threading.Thread(target=first_save, daemon=True)
    second = threading.Thread(target=second_save, daemon=True)
    first.start()
    try:
        assert locked.wait(5), result
        second.start()
        assert second_ready.wait(5), result
        blocked = _wait_for_blocker(
            lab_lock_engine, int(result["second_pid"]), second_finished
        )
        release.set()
        first.join(timeout=10)
        second.join(timeout=10)
        assert not first.is_alive() and not second.is_alive(), result
        assert blocked, "second save returned before the first transaction committed"
        assert result.get("first_status") == "IN_PROGRESS", result
        assert result.get("second_conflict") == 409, result
        assert "first_error" not in result and "second_error" not in result, result
    finally:
        release.set()
        first.join(timeout=10)
        second.join(timeout=10)
        assert not first.is_alive() and not second.is_alive(), result

    with Session(lab_lock_engine) as verification:
        stored = verification.get(LabReportInstance, instance_id)
        assert stored is not None
        assert stored.status == "IN_PROGRESS"
        assert [(value.field_key, value.value_text) for value in stored.values] == [
            ("wbc", "5.2")
        ]


def test_finalize_blocks_a_late_draft_save(
    lab_lock_engine,
    lab_instance_version,
):
    instance_id, original = lab_instance_version
    locked = threading.Event()
    release = threading.Event()
    save_ready = threading.Event()
    save_finished = threading.Event()
    result: dict[str, object] = {}

    def finalize_first() -> None:
        try:
            with Session(lab_lock_engine) as session:
                repository = _PausingLockRepository(session, locked, release)
                finalized = LabReportingService(
                    session, repository=repository
                ).finalize(instance_id)
                result["final_status"] = finalized.status
        except Exception as exc:  # noqa: BLE001 - surfaced in parent assertion
            result["final_error"] = repr(exc)

    def late_save() -> None:
        try:
            with Session(lab_lock_engine) as session:
                cached = session.get(LabReportInstance, instance_id)
                assert cached is not None and cached.status == "DRAFT"
                result["save_pid"] = session.scalar(text("SELECT pg_backend_pid()"))
                save_ready.set()
                LabReportingService(session).bulk_upsert_values(
                    instance_id,
                    [{"field_key": "wbc", "value_text": "9.9"}],
                    expected_updated_at=original.isoformat(),
                )
                result["save_status"] = "accepted"
        except LabReportingDomainError as exc:
            result["save_conflict"] = exc.status_code
        except Exception as exc:  # noqa: BLE001 - surfaced in parent assertion
            result["save_error"] = repr(exc)
        finally:
            save_finished.set()

    finalizer = threading.Thread(target=finalize_first, daemon=True)
    saver = threading.Thread(target=late_save, daemon=True)
    finalizer.start()
    try:
        assert locked.wait(5), result
        saver.start()
        assert save_ready.wait(5), result
        blocked = _wait_for_blocker(
            lab_lock_engine, int(result["save_pid"]), save_finished
        )
        release.set()
        finalizer.join(timeout=10)
        saver.join(timeout=10)
        assert not finalizer.is_alive() and not saver.is_alive(), result
        assert blocked, "draft save returned before finalize committed"
        assert result.get("final_status") == "FINALIZED", result
        assert result.get("save_conflict") == 409, result
        assert "final_error" not in result and "save_error" not in result, result
    finally:
        release.set()
        finalizer.join(timeout=10)
        saver.join(timeout=10)
        assert not finalizer.is_alive() and not saver.is_alive(), result

    with Session(lab_lock_engine) as verification:
        stored = verification.get(LabReportInstance, instance_id)
        assert stored is not None
        assert stored.status == "FINALIZED"
        assert stored.values == []
