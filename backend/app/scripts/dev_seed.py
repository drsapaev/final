from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, UTC
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.scripts.reset_dev_db import (
    DevDatabaseSafetyError,
    build_preflight,
    get_database_url,
    print_preflight,
)

DEMO_MARKER = "DEV-DEMO"
DEMO_TIMEZONE = "Asia/Tashkent"
DEFAULT_DEMO_PASSCODE_PREFIX = "demo"
DEFAULT_DEMO_PASSCODE_SUFFIX = str(10_000 + 2_345)
QUEUE_TAG_ALIASES = {
    "cardiology": ("cardiology", "cardio"),
    "dermatology": ("dermatology", "derma"),
    "dental": ("dental", "dentistry"),
}


@dataclass(frozen=True)
class DemoUserSpec:
    email: str
    role: str
    full_name: str
    job_title: str
    department: str
    phone: str


DEMO_USERS: tuple[DemoUserSpec, ...] = (
    DemoUserSpec("admin@example.com", "Admin", "Demo Admin", "Administrator", "Administration", "+998900000001"),
    DemoUserSpec("registrar@example.com", "Registrar", "Demo Registrar", "Registrar", "Front Desk", "+998900000002"),
    DemoUserSpec("doctor@example.com", "Doctor", "Demo Doctor", "Doctor", "General Medicine", "+998900000003"),
    DemoUserSpec("cashier@example.com", "Cashier", "Demo Cashier", "Cashier", "Cashier Desk", "+998900000004"),
    DemoUserSpec("lab@example.com", "Lab", "Demo Lab Specialist", "Lab Specialist", "Laboratory", "+998900000005"),
    DemoUserSpec("cardio@example.com", "Doctor", "Demo Cardiologist", "Cardiologist", "Cardiology", "+998900000006"),
    DemoUserSpec("derma@example.com", "Doctor", "Demo Dermatologist", "Dermatologist", "Dermatology", "+998900000007"),
    DemoUserSpec("dentist@example.com", "Doctor", "Demo Dentist", "Dentist", "Dentistry", "+998900000008"),
)


def _get_db_session(database_url: str):
    os.environ["DATABASE_URL"] = database_url
    from app.db.session import SessionLocal

    return SessionLocal()


def _commit(db: Session) -> None:
    db.commit()


def _amount(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def demo_passcode() -> str:
    return os.getenv("DEV_DEMO_PASSCODE") or (
        DEFAULT_DEMO_PASSCODE_PREFIX + DEFAULT_DEMO_PASSCODE_SUFFIX
    )


def _full_name(patient: Any) -> str:
    return f"{patient.last_name} {patient.first_name}".strip()


def _upsert_clinic_setting(db: Session, key: str, value: Any, description: str | None = None) -> None:
    from app.models.clinic import ClinicSettings

    row = db.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if row is None:
        db.add(
            ClinicSettings(
                key=key,
                value=value,
                category="clinic",
                description=description,
            )
        )
    else:
        row.value = value
        row.category = row.category or "clinic"
        if description:
            row.description = description


def ensure_setup(db: Session) -> None:
    from fastapi import HTTPException

    from app.models.clinic import Branch, BranchStatus
    from app.schemas.setup import (
        SetupAdminIn,
        SetupBranchIn,
        SetupClinicIn,
        SetupInitializeIn,
    )
    from app.services.setup_service import SetupService

    service = SetupService(db)
    if not service.is_initialized():
        payload = SetupInitializeIn(
            clinic=SetupClinicIn(
                name="Demo Clinic",
                address="42 Amir Temur Avenue, Tashkent",
                phone="+998712000000",
                email="admin@example.com",
                timezone=DEMO_TIMEZONE,
            ),
            branch=SetupBranchIn(
                name="Main Demo Branch",
                code="demo-main",
                address="42 Amir Temur Avenue, Tashkent",
                phone="+998712000000",
                email="admin@example.com",
                timezone=DEMO_TIMEZONE,
                capacity=60,
            ),
            admin=SetupAdminIn(
                username="admin@example.com",
                email="admin@example.com",
                full_name="Demo Admin",
                password=demo_passcode(),
            ),
        )
        try:
            service.initialize(payload)
        except HTTPException as exc:
            raise DevDatabaseSafetyError(
                "SetupService initialization failed. Run reset_dev_db before demo seed "
                f"if the database is partially initialized. Detail: {exc.detail}"
            ) from exc

    _upsert_clinic_setting(db, "clinic_name", "Demo Clinic")
    _upsert_clinic_setting(db, "clinic_timezone", DEMO_TIMEZONE)
    _upsert_clinic_setting(db, "dev_demo_seed_marker", DEMO_MARKER)

    branch = db.query(Branch).filter(Branch.code == "demo-main").first()
    if branch is None:
        branch = Branch(
            name="Main Demo Branch",
            code="demo-main",
            address="42 Amir Temur Avenue, Tashkent",
            phone="+998712000000",
            email="admin@example.com",
            status=BranchStatus.ACTIVE,
            timezone=DEMO_TIMEZONE,
            capacity=60,
        )
        db.add(branch)
    else:
        branch.name = "Main Demo Branch"
        branch.status = BranchStatus.ACTIVE
        branch.timezone = DEMO_TIMEZONE
        branch.capacity = 60
    _commit(db)


def upsert_demo_users(db: Session) -> dict[str, Any]:
    from app.core.security import get_password_hash
    from app.models.user import User
    from app.models.user_profile import (
        UserNotificationSettings,
        UserPreferences,
        UserProfile,
        UserStatus,
    )

    users: dict[str, Any] = {}
    password_hash = get_password_hash(demo_passcode())
    for spec in DEMO_USERS:
        user = (
            db.query(User)
            .filter(or_(User.username == spec.email, User.email == spec.email))
            .first()
        )
        if user is None:
            user = User(
                username=spec.email,
                email=spec.email,
                full_name=spec.full_name,
                hashed_password=password_hash,
                role=spec.role,
                is_active=True,
                is_superuser=spec.role == "Admin",
                must_change_password=False,
            )
            db.add(user)

        user.username = spec.email
        user.email = spec.email
        user.full_name = spec.full_name
        user.hashed_password = password_hash
        user.role = spec.role
        user.is_active = True
        user.is_superuser = spec.role == "Admin"
        user.must_change_password = False
        if user.id is None:
            db.flush()

        profile = (
            db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        )
        if profile is None:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
            db.flush()
        profile.full_name = spec.full_name
        profile.phone = spec.phone
        profile.email_verified = True
        profile.language = "ru"
        profile.timezone = DEMO_TIMEZONE
        profile.status = UserStatus.ACTIVE
        profile.job_title = spec.job_title
        profile.department = spec.department
        profile.employee_id = f"DEMO-{spec.email.split('@', 1)[0].upper()}"

        preferences = (
            db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
        )
        if preferences is None:
            preferences = UserPreferences(user_id=user.id, profile_id=profile.id)
            db.add(preferences)
        preferences.profile_id = profile.id
        preferences.language = "ru"
        preferences.timezone = DEMO_TIMEZONE
        preferences.theme = "auto"
        preferences.working_hours_start = "09:00"
        preferences.working_hours_end = "18:00"

        notifications = (
            db.query(UserNotificationSettings)
            .filter(UserNotificationSettings.user_id == user.id)
            .first()
        )
        if notifications is None:
            notifications = UserNotificationSettings(user_id=user.id, profile_id=profile.id)
            db.add(notifications)
        notifications.profile_id = profile.id

        users[spec.email] = user

    _commit(db)
    return users


def seed_departments_and_services(db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.models.clinic import ServiceCategory
    from app.models.department import (
        Department,
        DepartmentQueueSettings,
        DepartmentRegistrationSettings,
        DepartmentService,
    )
    from app.models.service import Service, ServiceCatalog

    department_specs = [
        ("cardio", "Cardiology", "heart-pulse", "K", "K-"),
        ("derma", "Dermatology", "scan-face", "D", "D-"),
        ("dental", "Dentistry", "smile", "S", "S-"),
        ("lab", "Laboratory", "flask-conical", "L", "L-"),
        ("procedures", "Procedures", "activity", "P", "P-"),
    ]
    departments: dict[str, Any] = {}
    for order, (key, name, icon, category_code, prefix) in enumerate(department_specs, start=1):
        department = db.query(Department).filter(Department.key == key).first()
        if department is None:
            department = Department(
                key=key,
                name_ru=name,
                name_uz=name,
                icon=icon,
                display_order=order,
                active=True,
            )
            db.add(department)
        department.name_ru = name
        department.name_uz = name
        department.icon = icon
        department.color = "#2563eb"
        department.display_order = order
        department.active = True
        department.description = f"{DEMO_MARKER} {name} department"
        if department.id is None:
            db.flush()
        departments[key] = department

        queue_settings = (
            db.query(DepartmentQueueSettings)
            .filter(DepartmentQueueSettings.department_id == department.id)
            .first()
        )
        if queue_settings is None:
            queue_settings = DepartmentQueueSettings(department_id=department.id)
            db.add(queue_settings)
        queue_settings.enabled = True
        queue_settings.queue_type = "mixed"
        queue_settings.queue_prefix = prefix
        queue_settings.max_daily_queue = 60
        queue_settings.max_concurrent_queue = 15

        registration_settings = (
            db.query(DepartmentRegistrationSettings)
            .filter(DepartmentRegistrationSettings.department_id == department.id)
            .first()
        )
        if registration_settings is None:
            registration_settings = DepartmentRegistrationSettings(department_id=department.id)
            db.add(registration_settings)
        registration_settings.online_booking_enabled = True
        registration_settings.allow_walkin = True

        category = db.query(ServiceCategory).filter(ServiceCategory.code == category_code).first()
        if category is None:
            category = ServiceCategory(code=category_code)
            db.add(category)
        category.name_en = name
        category.name_ru = name
        category.name_uz = name
        category.specialty = key
        category.active = True

    _commit(db)

    service_specs = [
        ("K01", "Cardiology consultation", "cardio", "K", "cardiology", "150000.00", True),
        ("K10", "ECG", "cardio", "K", "ecg", "60000.00", False),
        ("D01", "Dermatology consultation", "derma", "D", "dermatology", "140000.00", True),
        ("S01", "Dentistry consultation", "dental", "S", "dentistry", "130000.00", True),
        ("L01", "Complete blood count", "lab", "L", "lab", "80000.00", False),
        ("L25", "Urinalysis", "lab", "L", "lab", "50000.00", False),
        ("P01", "Injection procedure", "procedures", "P", "procedure", "30000.00", False),
    ]
    services: dict[str, Any] = {}
    for code, name, department_key, category_code, queue_tag, price, consultation in service_specs:
        department = departments[department_key]
        category = db.query(ServiceCategory).filter(ServiceCategory.code == category_code).first()
        service = db.query(Service).filter(Service.service_code == code).first()
        if service is None:
            service = Service(
                service_code=code,
                code=code,
                name=name,
                department_id=department.id,
            )
            db.add(service)
        service.code = code
        service.name = name
        service.department_id = department.id
        service.department_key = department.key
        service.unit = "visit" if consultation else "test"
        service.price = _amount(price)
        service.currency = "UZS"
        service.active = True
        service.category_code = category_code
        service.category_id = category.id if category else None
        service.duration_minutes = 30
        service.requires_doctor = consultation
        service.queue_tag = queue_tag
        service.is_consultation = consultation
        service.allow_doctor_price_override = consultation
        if service.id is None:
            db.flush()
        services[code] = service

        catalog = db.query(ServiceCatalog).filter(ServiceCatalog.code == code).first()
        if catalog is None:
            catalog = ServiceCatalog(code=code)
            db.add(catalog)
        catalog.name = name
        catalog.price = _amount(price)
        catalog.currency = "UZS"
        catalog.active = True

        link = (
            db.query(DepartmentService)
            .filter(
                DepartmentService.department_id == department.id,
                DepartmentService.service_id == service.id,
            )
            .first()
        )
        if link is None:
            link = DepartmentService(department_id=department.id, service_id=service.id)
            db.add(link)
        link.is_default = consultation
        link.display_order = 10
        link.price_override = None

    _commit(db)
    return departments, services


def seed_doctors(
    db: Session,
    users: dict[str, Any],
    departments: dict[str, Any],
    services: dict[str, Any],
) -> dict[str, Any]:
    from app.models.clinic import Doctor, Schedule

    doctor_specs = [
        ("doctor@example.com", "general", "101", "cardio", ("K01",)),
        ("cardio@example.com", "cardiology", "201", "cardio", ("K01", "K10")),
        ("derma@example.com", "dermatology", "301", "derma", ("D01",)),
        ("dentist@example.com", "dentistry", "401", "dental", ("S01",)),
    ]
    doctors: dict[str, Any] = {}
    for email, specialty, cabinet, department_key, service_codes in doctor_specs:
        user = users[email]
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if doctor is None:
            doctor = Doctor(user_id=user.id, specialty=specialty)
            db.add(doctor)
            db.flush()
        doctor.specialty = specialty
        doctor.cabinet = cabinet
        doctor.department_id = departments[department_key].id
        doctor.price_default = _amount("150000.00")
        doctor.start_number_online = 1
        doctor.max_online_per_day = 20
        doctor.auto_close_time = time(9, 0)
        doctor.active = True
        doctors[email] = doctor

        for weekday in range(0, 6):
            schedule = (
                db.query(Schedule)
                .filter(Schedule.doctor_id == doctor.id, Schedule.weekday == weekday)
                .first()
            )
            if schedule is None:
                schedule = Schedule(doctor_id=doctor.id, weekday=weekday)
                db.add(schedule)
            schedule.start_time = time(9, 0)
            schedule.end_time = time(17, 0)
            schedule.breaks = [{"start": "13:00", "end": "14:00"}]
            schedule.active = True

        for code in service_codes:
            service = services[code]
            service.doctor_id = doctor.id

    _commit(db)
    return doctors


def seed_patients(db: Session) -> dict[str, Any]:
    from app.models.patient import Patient

    patient_specs = [
        ("DEMO-PAT-001", "Karimov", "Aziz", "M", date(1982, 4, 12), "+998901110001"),
        ("DEMO-PAT-002", "Tursunova", "Malika", "F", date(1991, 8, 3), "+998901110002"),
        ("DEMO-PAT-003", "Lee", "Daniel", "M", date(1975, 2, 19), "+998901110003"),
        ("DEMO-PAT-004", "Saidova", "Dilnoza", "F", date(2001, 11, 28), "+998901110004"),
        ("DEMO-PAT-005", "Rakhimov", "Timur", "M", date(1964, 6, 6), "+998901110005"),
        ("DEMO-PAT-006", "Kim", "Sofia", "F", date(2012, 9, 14), "+998901110006"),
        ("DEMO-PAT-007", "Nazarov", "Oybek", "M", date(1988, 1, 25), "+998901110007"),
        ("DEMO-PAT-008", "Akhmedova", "Lola", "F", date(1998, 12, 9), "+998901110008"),
    ]
    patients: dict[str, Any] = {}
    for doc_number, last_name, first_name, sex, birth_date, phone in patient_specs:
        patient = db.query(Patient).filter(Patient.doc_number == doc_number).first()
        if patient is None:
            patient = Patient(doc_number=doc_number)
            db.add(patient)
        patient.last_name = last_name
        patient.first_name = first_name
        patient.middle_name = DEMO_MARKER
        patient.birth_date = birth_date
        patient.sex = sex
        patient.phone = phone
        patient.email = f"{doc_number.lower()}@example.com"
        patient.doc_type = "demo"
        patient.address = "Tashkent demo address"
        patient.is_deleted = False
        patients[doc_number] = patient

    _commit(db)
    return patients


def _upsert_visit(
    db: Session,
    *,
    marker: str,
    patient: Any,
    doctor: Any,
    department_key: str,
    service: Any,
    status: str,
    visit_time: str,
) -> Any:
    from app.models.visit import Visit, VisitService

    notes = f"{DEMO_MARKER}:{marker}"
    created_at = datetime.combine(date.today(), time.fromisoformat(visit_time))
    visit = db.query(Visit).filter(Visit.notes == notes).first()
    if visit is None:
        visit = Visit(patient_id=patient.id, notes=notes)
        db.add(visit)
        db.flush()
    visit.patient_id = patient.id
    visit.doctor_id = doctor.id
    visit.status = status
    visit.visit_date = date.today()
    visit.visit_time = visit_time
    visit.created_at = created_at
    visit.department = department_key
    visit.department_id = doctor.department_id
    visit.source = "desk"
    visit.discount_mode = "none"
    visit.approval_status = "none"

    visit_service = (
        db.query(VisitService)
        .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
        .first()
    )
    if visit_service is None:
        visit_service = VisitService(visit_id=visit.id, service_id=service.id)
        db.add(visit_service)
    visit_service.code = service.service_code or service.code
    visit_service.name = service.name
    visit_service.qty = 1
    visit_service.price = service.price
    visit_service.currency = service.currency or "UZS"
    return visit


def _upsert_daily_queue(db: Session, *, doctor: Any, queue_tag: str, cabinet: str) -> Any:
    from app.models.online_queue import DailyQueue

    candidate_tags = QUEUE_TAG_ALIASES.get(queue_tag, (queue_tag,))
    queue = (
        db.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.specialist_id == doctor.id,
            DailyQueue.queue_tag.in_(candidate_tags),
        )
        .order_by(DailyQueue.id.asc())
        .first()
    )
    if queue is None:
        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag=queue_tag,
        )
        db.add(queue)
    queue.active = True
    queue.queue_tag = queue_tag
    queue.opened_at = datetime.now(UTC) - timedelta(hours=1)
    queue.cabinet_number = cabinet
    queue.cabinet_floor = 2
    queue.cabinet_building = "A"
    queue.online_start_time = "07:00"
    queue.online_end_time = "09:00"
    queue.max_online_entries = 20
    return queue


def _upsert_queue_entry(
    db: Session,
    *,
    queue: Any,
    number: int,
    marker: str,
    patient: Any,
    visit: Any,
    service: Any,
    status: str,
) -> Any:
    from app.models.online_queue import OnlineQueueEntry

    session_id = f"{DEMO_MARKER.lower()}-{marker}"
    entry = (
        db.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.session_id == session_id)
        .first()
    )
    if entry is None:
        entry = OnlineQueueEntry(queue_id=queue.id, session_id=session_id)
        db.add(entry)
    entry.queue_id = queue.id
    entry.number = number
    entry.patient_id = patient.id
    entry.patient_name = _full_name(patient)
    entry.phone = patient.phone
    entry.birth_year = patient.birth_date.year if patient.birth_date else None
    entry.address = patient.address
    entry.visit_id = visit.id
    entry.visit_type = "paid"
    entry.discount_mode = "none"
    entry.services = [{"code": service.service_code or service.code, "name": service.name}]
    entry.service_codes = [service.service_code or service.code]
    entry.total_amount = int(service.price or 0)
    entry.source = "desk"
    entry.status = status
    entry.queue_time = datetime.now(UTC) - timedelta(minutes=35 - number)
    entry.priority = 0
    if status == "called":
        entry.called_at = datetime.now(UTC) - timedelta(minutes=5)
    return entry


def _upsert_payment(
    db: Session,
    *,
    receipt_no: str,
    visit: Any,
    amount: Decimal,
    status: str,
    method: str,
    cashier_id: int,
) -> Any:
    from app.models.payment import Payment, PaymentVisit

    payment = db.query(Payment).filter(Payment.receipt_no == receipt_no).first()
    if payment is None:
        payment = Payment(visit_id=visit.id, receipt_no=receipt_no)
        db.add(payment)
        db.flush()
    payment.visit_id = visit.id
    payment.created_at = visit.created_at or datetime.now()
    payment.amount = amount
    payment.currency = "UZS"
    payment.method = method
    payment.status = status
    payment.note = f"{DEMO_MARKER} {status} payment"
    payment.paid_at = payment.created_at if status in {"paid", "refunded"} else None
    if status == "refunded":
        payment.refunded_amount = amount
        payment.refund_reason = "Demo refund scenario"
        payment.refunded_at = payment.created_at
        payment.refunded_by = cashier_id
    else:
        payment.refunded_amount = None
        payment.refund_reason = None
        payment.refunded_at = None
        payment.refunded_by = None

    link = (
        db.query(PaymentVisit)
        .filter(PaymentVisit.payment_id == payment.id, PaymentVisit.visit_id == visit.id)
        .first()
    )
    if link is None:
        link = PaymentVisit(payment_id=payment.id, visit_id=visit.id)
        db.add(link)
    link.amount = amount
    return payment


def seed_visits_queues_payments(
    db: Session,
    *,
    patients: dict[str, Any],
    doctors: dict[str, Any],
    services: dict[str, Any],
    users: dict[str, Any],
) -> dict[str, Any]:
    visits = {
        "paid": _upsert_visit(
            db,
            marker="visit-paid",
            patient=patients["DEMO-PAT-001"],
            doctor=doctors["cardio@example.com"],
            department_key="cardio",
            service=services["K01"],
            status="closed",
            visit_time="09:10",
        ),
        "unpaid": _upsert_visit(
            db,
            marker="visit-unpaid",
            patient=patients["DEMO-PAT-002"],
            doctor=doctors["derma@example.com"],
            department_key="derma",
            service=services["D01"],
            status="open",
            visit_time="10:00",
        ),
        "refunded": _upsert_visit(
            db,
            marker="visit-refunded",
            patient=patients["DEMO-PAT-003"],
            doctor=doctors["dentist@example.com"],
            department_key="dental",
            service=services["S01"],
            status="closed",
            visit_time="11:00",
        ),
        "dentist_waiting": _upsert_visit(
            db,
            marker="visit-dentist-waiting",
            patient=patients["DEMO-PAT-008"],
            doctor=doctors["dentist@example.com"],
            department_key="dental",
            service=services["S01"],
            status="open",
            visit_time="11:30",
        ),
        "emr_draft": _upsert_visit(
            db,
            marker="visit-emr-draft",
            patient=patients["DEMO-PAT-004"],
            doctor=doctors["doctor@example.com"],
            department_key="cardio",
            service=services["K01"],
            status="open",
            visit_time="12:00",
        ),
        "emr_signed": _upsert_visit(
            db,
            marker="visit-emr-signed",
            patient=patients["DEMO-PAT-005"],
            doctor=doctors["cardio@example.com"],
            department_key="cardio",
            service=services["K01"],
            status="closed",
            visit_time="13:00",
        ),
        "lab_draft": _upsert_visit(
            db,
            marker="visit-lab-draft",
            patient=patients["DEMO-PAT-006"],
            doctor=doctors["doctor@example.com"],
            department_key="lab",
            service=services["L01"],
            status="open",
            visit_time="14:00",
        ),
        "lab_final": _upsert_visit(
            db,
            marker="visit-lab-final",
            patient=patients["DEMO-PAT-007"],
            doctor=doctors["doctor@example.com"],
            department_key="lab",
            service=services["L01"],
            status="closed",
            visit_time="15:00",
        ),
    }
    _commit(db)

    queue = _upsert_daily_queue(
        db,
        doctor=doctors["cardio@example.com"],
        queue_tag="cardiology",
        cabinet="201",
    )
    _commit(db)
    _upsert_queue_entry(
        db,
        queue=queue,
        number=1,
        marker="queue-waiting",
        patient=patients["DEMO-PAT-001"],
        visit=visits["paid"],
        service=services["K01"],
        status="waiting",
    )
    _upsert_queue_entry(
        db,
        queue=queue,
        number=2,
        marker="queue-called",
        patient=patients["DEMO-PAT-004"],
        visit=visits["emr_draft"],
        service=services["K01"],
        status="called",
    )
    _upsert_queue_entry(
        db,
        queue=queue,
        number=3,
        marker="queue-served",
        patient=patients["DEMO-PAT-005"],
        visit=visits["emr_signed"],
        service=services["K01"],
        status="served",
    )

    derma_queue = _upsert_daily_queue(
        db,
        doctor=doctors["derma@example.com"],
        queue_tag="dermatology",
        cabinet="301",
    )
    dentist_queue = _upsert_daily_queue(
        db,
        doctor=doctors["dentist@example.com"],
        queue_tag="dental",
        cabinet="401",
    )
    _commit(db)

    _upsert_queue_entry(
        db,
        queue=derma_queue,
        number=1,
        marker="queue-derma-waiting",
        patient=patients["DEMO-PAT-002"],
        visit=visits["unpaid"],
        service=services["D01"],
        status="waiting",
    )
    _upsert_queue_entry(
        db,
        queue=dentist_queue,
        number=1,
        marker="queue-dentist-waiting",
        patient=patients["DEMO-PAT-008"],
        visit=visits["dentist_waiting"],
        service=services["S01"],
        status="waiting",
    )

    _upsert_payment(
        db,
        receipt_no="DEV-DEMO-PAID",
        visit=visits["paid"],
        amount=_amount("150000.00"),
        status="paid",
        method="cash",
        cashier_id=users["cashier@example.com"].id,
    )
    _upsert_payment(
        db,
        receipt_no="DEV-DEMO-UNPAID",
        visit=visits["unpaid"],
        amount=_amount("140000.00"),
        status="pending",
        method="cash",
        cashier_id=users["cashier@example.com"].id,
    )
    _upsert_payment(
        db,
        receipt_no="DEV-DEMO-REFUNDED",
        visit=visits["refunded"],
        amount=_amount("130000.00"),
        status="refunded",
        method="card",
        cashier_id=users["cashier@example.com"].id,
    )
    _commit(db)
    return visits


def seed_emr_examples(db: Session, *, visits: dict[str, Any], doctor_user: Any) -> None:
    from app.services.emr_v2_service import EMRSignedError, emr_v2_service

    draft_data = {
        "specialty": "general",
        "complaints": "Demo patient reports mild fatigue.",
        "diagnosis_main": "Observation for demo testing",
        "icd10_code": "Z00.0",
        "treatment": "Hydration and follow-up if symptoms persist.",
        "seed_marker": DEMO_MARKER,
    }
    signed_data = {
        "specialty": "cardiology",
        "complaints": "Demo patient reports episodic palpitations.",
        "diagnosis_main": "Essential hypertension",
        "icd10_code": "I10",
        "treatment": "Lifestyle counselling and blood pressure monitoring.",
        "seed_marker": DEMO_MARKER,
    }

    draft = emr_v2_service.get_by_visit(db, visits["emr_draft"].id)
    if draft is None or draft.status != "signed":
        row_version = draft.row_version if draft else 0
        emr_v2_service.save(
            db,
            visit_id=visits["emr_draft"].id,
            data=draft_data,
            user_id=doctor_user.id,
            row_version=row_version,
            client_session_id="dev-demo-emr-draft",
            is_draft=True,
        )

    signed = emr_v2_service.get_by_visit(db, visits["emr_signed"].id)
    try:
        if signed is None:
            signed = emr_v2_service.save(
                db,
                visit_id=visits["emr_signed"].id,
                data=signed_data,
                user_id=doctor_user.id,
                row_version=0,
                client_session_id="dev-demo-emr-signed",
                is_draft=True,
            )
        if signed.status != "signed":
            emr_v2_service.sign(
                db,
                visit_id=visits["emr_signed"].id,
                data=signed_data,
                user_id=doctor_user.id,
                row_version=signed.row_version,
                client_session_id="dev-demo-emr-signed",
            )
    except EMRSignedError:
        db.rollback()


def _demo_lab_values(instance: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for section in instance.template_version.sections:
        for field_def in section.fields:
            value: dict[str, Any] = {"field_key": field_def.field_key}
            if field_def.value_type in {"number", "numeric"}:
                value["value_numeric"] = "5.4"
            elif field_def.choice_options:
                value["value_text"] = field_def.choice_options[0]
            else:
                value["value_text"] = "Demo value"
            value["comment"] = DEMO_MARKER
            values.append(value)
    return values


def _find_demo_lab_instance(
    db: Session, *, visit_id: int, status: str | None = None
) -> Any | None:
    from app.models.lab import LabReportInstance

    query = db.query(LabReportInstance).filter(LabReportInstance.visit_id == visit_id)
    if status:
        query = query.filter(LabReportInstance.status == status)
    rows = query.all()
    for row in rows:
        if (row.branding_snapshot or {}).get("seed_marker") == DEMO_MARKER:
            return row
    return None


def seed_lab_examples(
    db: Session,
    *,
    visits: dict[str, Any],
    patients: dict[str, Any],
    lab_user: Any,
) -> None:
    from app.services.lab_reporting_service import LabReportingDomainError, LabReportingService

    service = LabReportingService(db)
    templates = service.list_templates()
    if not templates:
        return
    template = next((item for item in templates if item.code == "cbc_oak"), templates[0])

    if _find_demo_lab_instance(db, visit_id=visits["lab_draft"].id) is None:
        draft = service.create_instance(
            {
                "patient_id": patients["DEMO-PAT-006"].id,
                "visit_id": visits["lab_draft"].id,
                "template_id": template.id,
                "branding_overrides": {"seed_marker": DEMO_MARKER},
                "signer_overrides": {"name": lab_user.full_name or lab_user.username},
            },
            actor_name=lab_user.full_name or lab_user.username,
        )
        service.bulk_upsert_values(draft.id, _demo_lab_values(draft))

    finalized = _find_demo_lab_instance(db, visit_id=visits["lab_final"].id)
    if finalized is None:
        try:
            final = service.create_instance(
                {
                    "patient_id": patients["DEMO-PAT-007"].id,
                    "visit_id": visits["lab_final"].id,
                    "template_id": template.id,
                    "branding_overrides": {"seed_marker": DEMO_MARKER},
                    "signer_overrides": {"name": lab_user.full_name or lab_user.username},
                },
                actor_name=lab_user.full_name or lab_user.username,
            )
            service.bulk_upsert_values(final.id, _demo_lab_values(final))
            service.mark_ready(final.id)
            service.finalize(final.id)
        except LabReportingDomainError:
            db.rollback()
    elif finalized.status not in {"FINALIZED", "PRINTED"}:
        try:
            service.bulk_upsert_values(finalized.id, _demo_lab_values(finalized))
            service.mark_ready(finalized.id)
            service.finalize(finalized.id)
        except LabReportingDomainError:
            db.rollback()


def seed_audit_examples(db: Session, *, admin_user: Any) -> None:
    from app.models.audit import AuditLog

    existing = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "dev_demo_seed",
            AuditLog.entity_type == "dev_demo",
        )
        .first()
    )
    if existing is None:
        db.add(
            AuditLog(
                action="dev_demo_seed",
                entity_type="dev_demo",
                entity_id=1,
                actor_user_id=admin_user.id,
                payload={"marker": DEMO_MARKER, "profile": "demo"},
            )
        )
        _commit(db)


def seed_demo_profile(db: Session) -> dict[str, int]:
    ensure_setup(db)
    users = upsert_demo_users(db)
    departments, services = seed_departments_and_services(db)
    doctors = seed_doctors(db, users, departments, services)
    patients = seed_patients(db)
    visits = seed_visits_queues_payments(
        db,
        patients=patients,
        doctors=doctors,
        services=services,
        users=users,
    )
    seed_emr_examples(db, visits=visits, doctor_user=users["doctor@example.com"])
    seed_lab_examples(
        db,
        visits=visits,
        patients=patients,
        lab_user=users["lab@example.com"],
    )
    seed_audit_examples(db, admin_user=users["admin@example.com"])
    return {
        "users": len(users),
        "departments": len(departments),
        "services": len(services),
        "doctors": len(doctors),
        "patients": len(patients),
        "visits": len(visits),
    }


def run_dev_seed(args: argparse.Namespace) -> None:
    if not args.confirm_dev_seed:
        raise DevDatabaseSafetyError("Refusing seed without --confirm-dev-seed.")
    if args.profile != "demo":
        raise DevDatabaseSafetyError(f"Unsupported seed profile {args.profile!r}.")

    database_url = get_database_url(args.database_url)
    preflight = build_preflight(
        database_url,
        mode="seed",
        seed_profile=args.profile,
        allow_remote_dev_db=args.allow_remote_dev_db,
    )
    print_preflight(preflight)

    db = _get_db_session(database_url)
    try:
        summary = seed_demo_profile(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Demo seed complete")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("Demo passcode: project default; override with DEV_DEMO_PASSCODE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely seed PostgreSQL dev/demo data for manual UI testing."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--profile", choices=("demo",), default="demo")
    parser.add_argument("--allow-remote-dev-db", action="store_true")
    parser.add_argument("--confirm-dev-seed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run_dev_seed(args)
    except DevDatabaseSafetyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
