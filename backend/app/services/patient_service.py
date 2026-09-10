from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes, log_critical_change
from app.core.i18n import t  # noqa: F401
from app.core.pii_masker import mask_pii
from app.core.roles import is_doctor_role_spelling
from app.crud import clinic as clinic_crud
from app.crud import visit as visit_crud
from app.crud.appointment import appointment as appointment_crud
from app.crud.patient import (
    normalize_patient_name,
    validate_birthdate,
)
from app.crud.patient import (
    patient as patient_crud,
)
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentHistoryItem
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.notifications import notification_sender_service
from app.services.patient_validation import PatientValidationService

logger = logging.getLogger(__name__)


class PatientReadAccessDenied(Exception):
    """Raised when a principal may not read the requested patient resource."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _dispatch_patient_registered_notification_async(
    *, patient_id: int, actor_id: int | None, registration_source: str
) -> None:
    """Run the patient_registered fan-out off the request path.

    Own session (the request session may be closed by the time the thread
    runs), own event loop via asyncio.run (legal in a fresh thread), and a
    logged-failure-only contract identical to the previous inline call.
    """
    import threading

    def _run() -> None:
        _run_patient_registered_notification(
            patient_id=patient_id,
            actor_id=actor_id,
            registration_source=registration_source,
        )

    try:
        threading.Thread(
            target=_run,
            name=f"patient-registered-notify-{patient_id}",
            daemon=True,
        ).start()
    except RuntimeError as exc:
        # Codex P2: the patient row is already COMMITTED — a thread-creation
        # failure (burst exhaustion) must not 500 a durable create. Log and
        # drop the best-effort fan-out.
        logger.warning(  # codeql[py/clear-text-logging-sensitive-data] — numeric surrogate id + error type only
            "[FIX:NOTIFICATIONS] patient_registered dispatch could not start a worker thread",
            extra={"patient_id": patient_id, "error_type": type(exc).__name__},
        )


def _run_patient_registered_notification(
    *, patient_id: int, actor_id: int | None, registration_source: str
) -> None:
    from app.db.session import SessionLocal

    db = None
    try:
        db = SessionLocal()
        patient = db.get(Patient, patient_id)
        if patient is None:
            logger.warning(  # codeql[py/clear-text-logging-sensitive-data] — numeric surrogate id only (no PHI fields), per AGENTS PII policy
                "[FIX:NOTIFICATIONS] patient_registered skipped: patient not found",
                extra={"patient_id": patient_id},
            )
            return
        actor_user = db.get(User, actor_id) if actor_id else None
        canonical_created = asyncio.run(
            notification_sender_service.send_patient_registered_notification(
                db=db,
                patient=patient,
                registration_source=registration_source,
                actor_user=actor_user,
            )
        )
        if not canonical_created:
            logger.warning(  # codeql[py/clear-text-logging-sensitive-data] — numeric surrogate ids only
                "[FIX:NOTIFICATIONS] patient_registered canonical delivery failed",
                extra={"patient_id": patient_id, "actor_id": actor_id},
            )
    except Exception as exc:
        logger.warning(  # codeql[py/clear-text-logging-sensitive-data] — numeric surrogate id + error type only
            "[FIX:NOTIFICATIONS] patient_registered background dispatch failed",
            extra={"patient_id": patient_id, "error_type": type(exc).__name__},
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.validation_service = PatientValidationService()

    def _doctor_allowed_doctor_ids(self, current_user: User) -> set[int]:
        doctor = clinic_crud.get_doctor_by_user_id(self.db, current_user.id)
        if doctor is None or not doctor.active:
            raise PatientReadAccessDenied("inactive_or_missing_doctor_profile")

        allowed_doctor_ids = {doctor.id}
        # Some legacy visit writers stored User.id in doctor_id. Keep that
        # compatibility only when the value cannot target another Doctor row.
        if clinic_crud.get_doctor_by_id(self.db, current_user.id) is None:
            allowed_doctor_ids.add(current_user.id)
        return allowed_doctor_ids

    def _allowed_doctor_ids_for_patient_read(
        self,
        *,
        current_user: User,
        patient_id: int,
    ) -> set[int] | None:
        if current_user.role == "Patient":
            current_patient = current_user.patient
            if current_patient is None or current_patient.id != patient_id:
                raise PatientReadAccessDenied("patient_self_scope_mismatch")

        if current_user.is_superuser or not is_doctor_role_spelling(
            current_user.role
        ):
            return None

        allowed_doctor_ids = self._doctor_allowed_doctor_ids(current_user)
        if not visit_crud.patient_has_visit_with_doctors(
            self.db,
            patient_id=patient_id,
            doctor_ids=allowed_doctor_ids,
        ):
            raise PatientReadAccessDenied("patient_not_assigned_to_doctor")
        return allowed_doctor_ids

    def list_patients_for_read(
        self,
        *,
        current_user: User,
        skip: int,
        limit: int,
        search_query: str | None,
        phone: str | None,
    ) -> list[Patient]:
        doctor_ids = None
        if (
            is_doctor_role_spelling(current_user.role)
            and not current_user.is_superuser
        ):
            doctor_ids = self._doctor_allowed_doctor_ids(current_user)
        return patient_crud.get_patients(
            self.db,
            skip=skip,
            limit=limit,
            search_query=search_query,
            phone=phone,
            doctor_ids=doctor_ids,
        )

    def get_patient_for_read(
        self,
        *,
        current_user: User,
        patient_id: int,
    ) -> Patient | None:
        self._allowed_doctor_ids_for_patient_read(
            current_user=current_user,
            patient_id=patient_id,
        )
        return patient_crud.get(self.db, id=patient_id)

    def get_patient_appointment_history_for_read(
        self,
        *,
        current_user: User,
        patient_id: int,
    ) -> tuple[Patient | None, list[AppointmentHistoryItem]]:
        doctor_ids = self._allowed_doctor_ids_for_patient_read(
            current_user=current_user,
            patient_id=patient_id,
        )
        patient = patient_crud.get(self.db, id=patient_id)
        if patient is None:
            return None, []

        appointments = appointment_crud.get_patient_history(
            self.db,
            patient_id=patient_id,
            doctor_ids=doctor_ids,
        )
        return patient, [
            AppointmentHistoryItem(
                id=appointment.id,
                appointment_date=appointment.appointment_date,
                appointment_time=appointment.appointment_time,
                department=(
                    appointment.department.key or appointment.department.name_ru
                    if appointment.department is not None
                    else None
                ),
                doctor_id=appointment.doctor_id,
                status=appointment.status,
                notes=appointment.notes,
            )
            for appointment in appointments
        ]

    def create_patient(
        self,
        *,
        request: Request,
        patient_in: PatientCreate,
        current_user: User,
    ) -> Patient:
        if patient_in.phone:
            existing_patient = patient_crud.get_patient_by_phone(
                self.db, phone=patient_in.phone
            )
            if existing_patient:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером телефона уже существует",
                )

        if patient_in.doc_number:
            existing_by_doc = (
                self.db.query(Patient)
                .filter(Patient.doc_number == patient_in.doc_number)
                .first()
            )
            if existing_by_doc:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером документа уже зарегистрирован",
                )

        has_full_name = patient_in.full_name and patient_in.full_name.strip()
        has_individual_names = (
            patient_in.last_name and patient_in.last_name.strip()
        ) or (patient_in.first_name and patient_in.first_name.strip())

        if not has_full_name and not has_individual_names:
            raise HTTPException(
                status_code=422,
                detail="Необходимо указать либо полное ФИО (full_name), либо фамилию и имя (last_name, first_name)",
            )

        name_parts = normalize_patient_name(
            full_name=patient_in.full_name.strip() if has_full_name else None,
            last_name=(
                patient_in.last_name.strip()
                if (patient_in.last_name and patient_in.last_name.strip())
                else None
            ),
            first_name=(
                patient_in.first_name.strip()
                if (patient_in.first_name and patient_in.first_name.strip())
                else None
            ),
            middle_name=(
                patient_in.middle_name.strip()
                if (patient_in.middle_name and patient_in.middle_name.strip())
                else None
            ),
        )

        patient_in.last_name = name_parts["last_name"] or ""
        patient_in.first_name = name_parts["first_name"] or ""
        patient_in.middle_name = name_parts.get("middle_name") or None
        if name_parts.get("full_name"):
            patient_in.full_name = name_parts["full_name"]

        patient_dict = patient_in.model_dump(exclude_unset=True)
        patient_dict = self.validation_service.sanitize_patient_data(patient_dict)
        is_valid, errors = self.validation_service.validate_patient_data(patient_dict)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail=f"Validation errors: {'; '.join(errors)}",
            )

        for key, value in patient_dict.items():
            if hasattr(patient_in, key):
                setattr(patient_in, key, value)

        normalized_last_name = (name_parts["last_name"] or "").strip()
        normalized_first_name = (name_parts["first_name"] or "").strip()
        normalized_middle_name = name_parts.get("middle_name")

        # Codex round-16 P1: имена пациента -- PII (AGENTS.md L391-408),
        # в debug-лог попадают только длины/факт наличия, не значения
        # (тот же принцип, что и для doc_number в round-15).
        logger.debug(
            "Нормализация имени пациента: full_name_len=%d, last_name_len=%d, "
            "first_name_len=%d, middle_name_present=%s",
            len(patient_in.full_name or ""),
            len(patient_in.last_name or ""),
            len(patient_in.first_name or ""),
            bool(normalized_middle_name),
        )

        if not normalized_last_name:
            raise HTTPException(
                status_code=422,
                detail="Фамилия пациента обязательна для заполнения и не может быть пустой",
            )
        if not normalized_first_name:
            raise HTTPException(
                status_code=422,
                detail="Имя пациента обязательно для заполнения и не может быть пустым",
            )

        if patient_in.birth_date and not validate_birthdate(patient_in.birth_date):
            raise HTTPException(status_code=400, detail="Некорректная дата рождения")

        # Codex round-15 P1: doc_number -- full-redact PII (AGENTS.md
        # L390-407); сам номер в лог не попадает НИ В КАКОМ виде (ни
        # сырым, ни маскированным -- CodeQL flagged the masked variant as
        # clear-text logging, т.к. поток значения непрозрачен маске):
        # логируем только тип документа и факт его наличия.
        logger.debug(
            "[FIX:ADM-05] Persisting patient document fields",
            extra={
                "doc_type": patient_in.doc_type,
                "has_doc_number": patient_in.doc_number is not None,
            },
        )

        validated_patient = PatientCreate(
            last_name=normalized_last_name,
            first_name=normalized_first_name,
            middle_name=normalized_middle_name,
            birth_date=patient_in.birth_date,
            sex=patient_in.sex,
            phone=patient_in.phone,
            email=patient_in.email,
            doc_type=patient_in.doc_type,
            doc_number=patient_in.doc_number,
            address=patient_in.address,
        )

        patient = patient_crud.create(db=self.db, obj_in=validated_patient)
        self.db.refresh(patient)
        if not patient.last_name or not patient.last_name.strip():
            raise HTTPException(
                status_code=500,
                detail="Ошибка сохранения: фамилия пациента не была сохранена",
            )
        if not patient.first_name or not patient.first_name.strip():
            raise HTTPException(
                status_code=500,
                detail="Ошибка сохранения: имя пациента не было сохранено",
            )

        # Codex round-10 P1: JSON-снапшоты аудита хранят PHI в plaintext —
        # маскируем каноническим pii_masker (AGENTS.md L390-407).
        # extract_model_changes возвращает КОРТЕЖ (old, new) — маскируем
        # ПОСЛЕ распаковки (mask_pii не рекурсирует в tuple).
        _, new_data = extract_model_changes(None, patient)
        new_data = mask_pii(new_data)
        log_critical_change(
            db=self.db,
            user_id=current_user.id,
            action="CREATE",
            table_name="patients",
            row_id=patient.id,
            old_data=None,
            new_data=new_data,
            request=request,
            # Codex round-9 P1: initial-only режим аудита — вместо ФИО
            # идентифицируем пациента ID (AGENTS.md L390-407).
            description=f"Создан пациент #{patient.id}",
        )
        self.db.commit()
        # Perf (P0 2026-09-04): the registration fan-out (role-target lookups,
        # profiles, deliveries) costs dozens of remote-DB roundtrips — it ran
        # SYNCHRONOUSLY in the request and made patient creation take 15-30s.
        # Dispatched to a daemon thread with its own session AFTER the commit:
        # the patient row is already durable, and notifications are
        # best-effort by contract (the previous try/except only logged).
        registration_source = (
            "self_service"
            if str(getattr(current_user, "role", "")).lower() == "patient"
            else "registrar_panel"
        )
        try:
            _request_bind_is_sqlite = (
                self.db.get_bind().dialect.name == "sqlite"
            )
        except Exception:
            _request_bind_is_sqlite = False

        if _request_bind_is_sqlite:
            # Test container: run inline on the REQUEST session — the
            # historical semantics (the test database only exists inside
            # the request's session scope, and a background SessionLocal
            # would race it with "database is locked").
            try:
                canonical_created = asyncio.run(
                    notification_sender_service.send_patient_registered_notification(
                        db=self.db,
                        patient=patient,
                        registration_source=registration_source,
                        actor_user=current_user,
                    )
                )
                if not canonical_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] patient_registered canonical delivery failed",
                        extra={"patient_id": patient.id, "actor_id": current_user.id},
                    )
            except Exception as exc:
                logger.warning(
                    "[FIX:NOTIFICATIONS] patient_registered dispatch failed",
                    extra={
                        "patient_id": patient.id,
                        "actor_id": current_user.id,
                        "error_type": type(exc).__name__,
                    },
                )
                # A swallowed DB error would leave the session in a
                # rollback-required state that leaks into the next request
                # on this connection (test savepoint contamination).
                try:
                    self.db.rollback()
                except Exception:
                    pass
        else:
            # Production Postgres: fan-out off the request path.
            _dispatch_patient_registered_notification_async(
                patient_id=patient.id,
                actor_id=getattr(current_user, "id", None),
                registration_source=registration_source,
            )
        return patient

    def update_patient(
        self,
        *,
        request: Request,
        patient_id: int,
        patient_in: PatientUpdate,
        current_user: User,
    ) -> Patient:
        patient = patient_crud.get(self.db, id=patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=t("patient.not_found"))

        if patient_in.phone and patient_in.phone != patient.phone:
            existing_patient = patient_crud.get_patient_by_phone(
                self.db, phone=patient_in.phone
            )
            if existing_patient and existing_patient.id != patient_id:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером телефона уже существует",
                )

        # Codex round-15 P1: дубликат doc_number при обновлении -- тот же
        # контракт, что и при создании (patients.doc_number без unique-
        # констрейнта; поиск по документу через .first() стал бы
        # неоднозначным). Исключаем текущего пациента (unchanged value).
        if patient_in.doc_number and patient_in.doc_number != patient.doc_number:
            existing_by_doc = (
                self.db.query(Patient)
                .filter(Patient.doc_number == patient_in.doc_number)
                .first()
            )
            if existing_by_doc and existing_by_doc.id != patient_id:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером документа уже зарегистрирован",
                )

        # Codex round-10 P1: маскируем PHI в old-снапшоте (см. create;
        # extract_model_changes -> кортеж, маскируем после распаковки).
        old_data, _ = extract_model_changes(patient, None)
        old_data = mask_pii(old_data)

        # Fix B (wizard profile save): PatientUpdate теперь принимает full_name.
        # Нормализуем его в last_name/first_name/middle_name той же функцией,
        # что и при создании (SSOT: normalize_patient_name), и НЕ передаём
        # schema-only поле в CRUD — у ORM-модели full_name это read-only
        # hybrid property, setattr затирал бы её в экземпляре.
        update_payload = patient_in.model_dump(exclude_unset=True)
        raw_full_name = update_payload.pop("full_name", None)
        if raw_full_name is not None and str(raw_full_name).strip():
            name_parts = normalize_patient_name(full_name=str(raw_full_name).strip())
            update_payload["last_name"] = name_parts.get("last_name") or None
            update_payload["first_name"] = name_parts.get("first_name") or None
            update_payload["middle_name"] = name_parts.get("middle_name") or None

            # Codex R2 #3090 (P2): full_name ограничен 255 символами в схеме,
            # но колонки last_name/first_name/middle_name — varchar(128).
            # Компонент длиной 129+ символов (ФИО-инпут визарда без maxLength)
            # проходил схему и падал на уровне БД (500) вместо 422-валидации.
            _NAME_PART_MAX = 128
            for _part in ("last_name", "first_name", "middle_name"):
                _value = update_payload.get(_part)
                if _value is not None and len(str(_value)) > _NAME_PART_MAX:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Часть ФИО «{_part}» превышает {_NAME_PART_MAX} символов "
                            f"({len(str(_value))}). Разбейте ФИО или сократите."
                        ),
                    )

        patient = patient_crud.update(db=self.db, db_obj=patient, obj_in=update_payload)
        self.db.refresh(patient)

        _, new_data = extract_model_changes(None, patient)
        new_data = mask_pii(new_data)
        log_critical_change(
            db=self.db,
            user_id=current_user.id,
            action="UPDATE",
            table_name="patients",
            row_id=patient.id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            # Codex round-9 P1: вместо ФИО — ID пациента
            description=f"Обновлен пациент #{patient.id}",
        )
        self.db.commit()

        return patient

    def delete_patient(
        self,
        *,
        request: Request,
        patient_id: int,
        current_user: User,
    ) -> dict[str, str]:
        patient = patient_crud.get(self.db, id=patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail=t("patient.not_found"))

        if patient_crud.has_active_appointments(self.db, patient_id=patient_id):
            raise HTTPException(
                status_code=400, detail="Нельзя удалить пациента с активными записями"
            )

        # Codex round-10 P1: маскируем PHI в old-снапшоте (см. create).
        old_data, _ = extract_model_changes(patient, None)
        old_data = mask_pii(old_data)

        try:
            patient_crud.remove(db=self.db, id=patient_id)
            log_critical_change(
                db=self.db,
                user_id=current_user.id,
                action="DELETE",
                table_name="patients",
                row_id=patient_id,
                old_data=old_data,
                new_data=None,
                request=request,
                # Codex round-9 P1: вместо ФИО — ID пациента
                description=f"Удален пациент #{patient_id}",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка",
            )

        return {"message": "Пациент успешно удален"}
