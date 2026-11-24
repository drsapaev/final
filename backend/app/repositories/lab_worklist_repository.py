"""Read model for the clinic's cross-day laboratory worklist."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Date,
    Integer,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    null,
    or_,
    select,
    tuple_,
    type_coerce,
    union_all,
)
from sqlalchemy.orm import aliased

from app.models.appointment import Appointment
from app.models.department import Department
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabOrderTest,
    LabReportInstance,
    LabReportTemplate,
)
from app.models.lab_specimen import LabSpecimen
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.visit import Visit
from app.repositories.lab_ordered_test_repository import (
    INACTIVE_LAB_VISIT_STATUSES,
    LAB_DEPARTMENT_HINTS,
    active_lab_orders,
    lab_visit_services,
    unallocated_lab_report_visits,
)
from app.schemas.lab_worklist import (
    LabWorklistCounts,
    LabWorklistEntry,
    LabWorklistPage,
    LabWorklistProgress,
    LabWorklistSearch,
    LabWorklistService,
)
from app.services.service_mapping import normalize_service_code

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_PENDING_TICKETS = (
    "waiting",
    "called",
    "paid",
    "in_service",
    "diagnostics",
    "incomplete",
)
_REVIEW_STATUSES = ("READY", "IN_REVIEW", "REVIEWED")
_SOURCE_TYPES = ("appointment", "order", "queue", "visit")


class InvalidWorklistCursor(ValueError):
    """A cursor belongs to a different search or missing anchor."""


def _lab_queue():
    return or_(
        QueueResource.queue_tag == "lab",
        and_(
            DailyQueue.queue_resource_id.is_(None),
            DailyQueue.queue_tag.in_(("lab", "laboratory")),
        ),
    )


def _lab_tickets():
    return (
        select(
            OnlineQueueEntry.id,
            OnlineQueueEntry.visit_id,
            OnlineQueueEntry.patient_id,
            OnlineQueueEntry.number,
            OnlineQueueEntry.status,
            DailyQueue.day,
            func.coalesce(
                OnlineQueueEntry.queue_time, OnlineQueueEntry.created_at
            ).label("created_at"),
        )
        .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
        .outerjoin(QueueResource, QueueResource.id == DailyQueue.queue_resource_id)
        .where(_lab_queue())
        .cte("lab_tickets")
    )


def _local_day(db: Session, timestamp, now: datetime):
    if db.get_bind().dialect.name == "postgresql":
        return cast(func.timezone(now.tzinfo.key, timestamp), Date)
    # SQLite is used for narrow query-shape tests. Production evaluates the
    # IANA zone in PostgreSQL for each instant, including offset transitions.
    offset_minutes = int(now.utcoffset().total_seconds() / 60)
    return type_coerce(func.date(timestamp, f"{offset_minutes:+d} minutes"), Date)


def _work_rows(db: Session, visit_services, tickets, now: datetime):
    unallocated = ~exists().where(
        LabOrderTest.visit_service_id == visit_services.c.visit_service_id
    )
    visit_has_unallocated = exists(
        select(1)
        .select_from(visit_services)
        .where(
            visit_services.c.visit_id == Visit.id,
            unallocated,
        )
    )
    visit_has_order = exists().where(LabOrder.visit_id == Visit.id)
    # A ticket is display metadata only when linked to this exact visit and
    # patient. A newer encounter of the same patient is a different work item.
    visit_ticket_id = (
        select(tickets.c.id)
        .where(tickets.c.visit_id == Visit.id, tickets.c.patient_id == Visit.patient_id)
        .order_by(tickets.c.day.desc(), tickets.c.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    visit_lab_department = or_(
        func.lower(func.trim(Visit.department)).in_(LAB_DEPARTMENT_HINTS),
        Department.key.in_(LAB_DEPARTMENT_HINTS),
        visit_ticket_id.is_not(None),
    )
    visible_visit = ~func.lower(Visit.status).in_(INACTIVE_LAB_VISIT_STATUSES)
    order_time = func.coalesce(Visit.created_at, LabOrder.created_at)
    orders = (
        select(
            literal("order").label("source"),
            LabOrder.id.label("source_id"),
            LabOrder.id.label("order_id"),
            LabOrder.visit_id.label("visit_id"),
            cast(null(), Integer).label("appointment_id"),
            visit_ticket_id.label("queue_entry_id"),
            func.coalesce(LabOrder.patient_id, Visit.patient_id).label("patient_id"),
            func.coalesce(Visit.visit_date, _local_day(db, order_time, now)).label(
                "work_date"
            ),
            Visit.visit_time.label("appointment_time"),
            LabOrder.created_at.label("created_at"),
            LabOrder.due_at,
            LabOrder.priority,
            LabOrder.status.label("order_status"),
        )
        .select_from(LabOrder)
        .outerjoin(Visit, Visit.id == LabOrder.visit_id)
        .where(
            ~func.lower(LabOrder.status).in_(INACTIVE_LAB_VISIT_STATUSES),
            or_(LabOrder.visit_id.is_(None), visible_visit),
            or_(
                LabOrder.patient_id.is_(None),
                LabOrder.visit_id.is_(None),
                LabOrder.patient_id == Visit.patient_id,
            ),
        )
    )
    visits = (
        select(
            literal("visit"),
            Visit.id,
            null(),
            Visit.id,
            null(),
            visit_ticket_id,
            Visit.patient_id,
            func.coalesce(Visit.visit_date, _local_day(db, Visit.created_at, now)),
            Visit.visit_time,
            Visit.created_at,
            null(),
            null(),
            null(),
        )
        .select_from(Visit)
        .outerjoin(Department, Department.id == Visit.department_id)
        .where(
            visible_visit,
            or_(visit_has_unallocated, and_(visit_lab_department, ~visit_has_order)),
        )
    )
    # The historical booking bridge resolves by patient, slot and doctor.
    # Suppress the appointment row when it already has a candidate visit.
    visit_slot = exists(
        select(1)
        .select_from(Visit)
        .where(
            Visit.patient_id == Appointment.patient_id,
            Visit.visit_date == Appointment.appointment_date,
            func.substr(Visit.visit_time, 1, 5).is_not_distinct_from(
                func.substr(Appointment.appointment_time, 1, 5)
            ),
            Visit.doctor_id.is_not_distinct_from(Appointment.doctor_id),
        )
    )
    appointments = (
        select(
            literal("appointment"),
            Appointment.id,
            null(),
            null(),
            Appointment.id,
            null(),
            Appointment.patient_id,
            Appointment.appointment_date,
            Appointment.appointment_time,
            Appointment.created_at,
            null(),
            null(),
            null(),
        )
        .join(Department, Department.id == Appointment.department_id)
        .where(
            Department.key.in_(LAB_DEPARTMENT_HINTS),
            ~func.lower(Appointment.status).in_(INACTIVE_LAB_VISIT_STATUSES),
            ~visit_slot,
        )
    )
    previsit_tickets = select(
        literal("queue"),
        tickets.c.id,
        null(),
        null(),
        null(),
        tickets.c.id,
        tickets.c.patient_id,
        tickets.c.day,
        null(),
        tickets.c.created_at,
        null(),
        null(),
        null(),
    ).where(tickets.c.visit_id.is_(None), tickets.c.status.in_(_PENDING_TICKETS))
    return union_all(orders, visits, appointments, previsit_tickets).cte(
        "lab_work_rows"
    )


def _key(base):
    return base.c.source, base.c.source_id


def _reports(base):
    # Only revisions in the same order/visit/patient context contribute.
    # Group by chain root: a new correction draft never doubles the report
    # count or erases the previous release while the correction is pending.
    report = LabReportInstance
    roots = (
        select(
            base.c.source,
            base.c.source_id,
            report.id.label("root_id"),
            report.id,
            report.visit_id,
            report.order_id,
            report.patient_id,
            report.template_id,
            report.status,
        )
        .join_from(
            base,
            report,
            and_(
                report.patient_id == base.c.patient_id,
                report.visit_id.is_not_distinct_from(base.c.visit_id),
                or_(
                    and_(base.c.source == "order", report.order_id == base.c.order_id),
                    and_(base.c.source == "visit", report.order_id.is_(None)),
                ),
            ),
        )
        .where(report.supersedes_instance_id.is_(None))
        .cte("lab_report_chains", recursive=True)
    )
    revisions = roots.union_all(
        select(
            roots.c.source,
            roots.c.source_id,
            roots.c.root_id,
            report.id,
            report.visit_id,
            report.order_id,
            report.patient_id,
            report.template_id,
            report.status,
        ).join_from(
            roots,
            report,
            and_(
                report.supersedes_instance_id == roots.c.id,
                report.order_id.is_not_distinct_from(roots.c.order_id),
                report.visit_id.is_not_distinct_from(roots.c.visit_id),
                report.patient_id == roots.c.patient_id,
                report.template_id == roots.c.template_id,
            ),
        )
    )
    child = aliased(LabReportInstance)
    head = ~exists().where(
        child.supersedes_instance_id == revisions.c.id,
        child.order_id.is_not_distinct_from(revisions.c.order_id),
        child.visit_id.is_not_distinct_from(revisions.c.visit_id),
        child.patient_id == revisions.c.patient_id,
        child.template_id == revisions.c.template_id,
    )
    chains = (
        select(
            *_key(revisions),
            revisions.c.root_id,
            func.max(
                case((revisions.c.status.in_(FINAL_INSTANCE_STATUSES), 1), else_=0)
            ).label("released"),
            func.max(
                case((and_(head, revisions.c.status.in_(_REVIEW_STATUSES)), 1), else_=0)
            ).label("in_review"),
            func.max(
                case(
                    (and_(head, ~revisions.c.status.in_(FINAL_INSTANCE_STATUSES)), 1),
                    else_=0,
                )
            ).label("unfinished"),
            func.max(
                case(
                    (
                        and_(head, revisions.c.status.in_(_REVIEW_STATUSES)),
                        revisions.c.id,
                    )
                )
            ).label("review_id"),
            func.max(
                case(
                    (
                        and_(head, ~revisions.c.status.in_(FINAL_INSTANCE_STATUSES)),
                        revisions.c.id,
                    )
                )
            ).label("active_id"),
            func.max(case((head, revisions.c.id))).label("latest_id"),
        )
        .group_by(*_key(revisions), revisions.c.root_id)
        .cte("lab_report_chain_facts")
    )
    rollup = (
        select(
            *_key(chains),
            func.count().label("total_reports"),
            func.sum(chains.c.released).label("released_reports"),
            func.sum(chains.c.in_review).label("in_review"),
            func.sum(chains.c.unfinished).label("unfinished"),
            func.coalesce(
                func.max(chains.c.review_id),
                func.max(chains.c.active_id),
                func.max(chains.c.latest_id),
            ).label("report_id"),
        )
        .group_by(*_key(chains))
        .cte("lab_reports_by_work_row")
    )
    return chains, rollup, revisions


def _test_rollup(chains):
    return (
        select(
            LabOrderTest.order_id,
            func.count().label("ordered_tests"),
            func.sum(func.coalesce(chains.c.released, 0)).label("released_tests"),
            func.count()
            .filter(LabOrderTest.canceled_at.is_not(None))
            .label("canceled_tests"),
        )
        .outerjoin(
            chains,
            and_(
                chains.c.source == "order",
                chains.c.source_id == LabOrderTest.order_id,
                chains.c.root_id == LabOrderTest.report_instance_id,
            ),
        )
        .group_by(LabOrderTest.order_id)
        .cte("lab_tests_by_order")
    )


def _specimen_rollup():
    replacement = aliased(LabSpecimen)
    return (
        select(
            LabSpecimen.order_id,
            func.count().filter(LabSpecimen.status == "held").label("held"),
            func.count().filter(LabSpecimen.status == "rejected").label("rejected"),
            func.count().filter(LabSpecimen.status == "expected").label("expected"),
        )
        .where(~exists().where(replacement.replaces_specimen_id == LabSpecimen.id))
        .group_by(
            LabSpecimen.order_id,
        )
        .cte("current_specimen_facts")
    )


def _services_for_row(base, visit_services):
    allocation = exists().where(
        LabOrderTest.visit_service_id == visit_services.c.visit_service_id
    )
    order_allocation = (
        exists()
        .where(
            LabOrderTest.visit_service_id == visit_services.c.visit_service_id,
            LabOrderTest.order_id == base.c.order_id,
        )
        .correlate(base, visit_services)
    )
    return and_(
        visit_services.c.visit_id == base.c.visit_id,
        or_(
            and_(base.c.source == "visit", ~allocation),
            and_(base.c.source == "order", order_allocation),
        ),
    )


def _search_predicate(db: Session, payload, base, visit_services, revisions):
    term = payload.q.strip()
    specimen_matches = select(1).where(LabSpecimen.order_id == base.c.order_id)
    criteria = []
    if payload.barcode:
        criteria.append(
            exists(
                specimen_matches.where(LabSpecimen.barcode == payload.barcode.upper())
            )
        )
    if not term:
        return criteria

    words = term.casefold().split()
    patient_name = func.lower(Patient.full_name)
    service_text = exists(
        select(1)
        .select_from(visit_services)
        .where(
            _services_for_row(base, visit_services),
            or_(
                func.lower(visit_services.c.name).contains(
                    term.casefold(), autoescape=True
                ),
                func.lower(visit_services.c.code).contains(
                    term.casefold(), autoescape=True
                ),
            ),
        )
    )
    barcode_match = exists(specimen_matches.where(LabSpecimen.barcode == term.upper()))
    matches = [
        and_(*(patient_name.contains(word, autoescape=True) for word in words)),
        service_text,
        barcode_match,
    ]
    if all(char in "+0123456789 ()-" for char in term):
        digits = "".join(char for char in term if char.isdecimal())
        if len(digits) >= 4:
            if db.get_bind().dialect.name == "postgresql":
                phone_digits = func.regexp_replace(Patient.phone, "[^0-9]", "", "g")
            else:
                phone_digits = Patient.phone
                for separator in "+ ()-":
                    phone_digits = func.replace(phone_digits, separator, "")
            matches.append(phone_digits.contains(digits))
    identity_columns = {
        "patient": base.c.patient_id,
        "visit": base.c.visit_id,
        "appointment": base.c.appointment_id,
        "order": base.c.order_id,
        "queue": base.c.queue_entry_id,
    }
    namespace, colon, identifier = term.casefold().partition(":")
    digits = identifier if colon else namespace
    if (
        digits.isascii()
        and digits.isdecimal()
        and len(digits) <= 10
        and int(digits) <= 2_147_483_647
    ):
        exact_id = int(digits)
        if not colon:
            matches.extend(column == exact_id for column in identity_columns.values())
        elif namespace in identity_columns:
            matches.append(identity_columns[namespace] == exact_id)
        if namespace == "specimen" or not colon:
            matches.append(exists(specimen_matches.where(LabSpecimen.id == exact_id)))
        if namespace == "report" or not colon:
            matches.append(
                exists(
                    select(1)
                    .select_from(revisions)
                    .where(
                        revisions.c.source == base.c.source,
                        revisions.c.source_id == base.c.source_id,
                        revisions.c.id == exact_id,
                    )
                )
            )
    return [*criteria, or_(*matches)]


def _filtered_work_rows(db: Session, payload: LabWorklistSearch, now: datetime):
    visit_services = lab_visit_services(include_previously_allocated=True).cte(
        "lab_visit_services"
    )
    tickets = _lab_tickets()
    base = _work_rows(db, visit_services, tickets, now)
    chains, reports, revisions = _reports(base)
    tests = _test_rollup(chains)
    specimens = _specimen_rollup()
    total_reports = func.coalesce(reports.c.total_reports, 0)
    released_reports = func.coalesce(reports.c.released_reports, 0)
    unfinished = func.coalesce(reports.c.unfinished, 0)
    remaining_tests = (
        tests.c.ordered_tests - tests.c.released_tests - tests.c.canceled_tests
    )
    hold = case(
        (specimens.c.held > 0, "specimen_held"),
        (specimens.c.rejected > 0, "specimen_rejected"),
    )
    ready = and_(
        unfinished == 0,
        or_(
            and_(
                tests.c.ordered_tests.is_not(None),
                remaining_tests == 0,
                released_reports > 0,
            ),
            and_(
                tests.c.ordered_tests.is_(None),
                base.c.source == "order",
                total_reports > 0,
                total_reports == released_reports,
            ),
            and_(
                tests.c.ordered_tests.is_(None),
                total_reports == 0,
                base.c.order_status == "done",
            ),
        ),
    )
    status = case(
        (
            and_(tests.c.canceled_tests == tests.c.ordered_tests, total_reports == 0),
            "canceled",
        ),
        (ready, "ready"),
        (hold.is_not(None), "held"),
        (reports.c.in_review > 0, "in_review"),
        (specimens.c.expected > 0, "awaiting_specimen"),
        (released_reports > 0, "partial"),
        (unfinished > 0, "in_progress"),
        else_="pending",
    ).label("status")
    selected_report = aliased(LabReportInstance)
    stmt = (
        select(
            *base.c,
            Patient.full_name.label("patient_fio"),
            Patient.birth_date,
            func.lower(Patient.full_name).label("name_sort"),
            tickets.c.number.label("queue_number"),
            tickets.c.status.label("queue_status"),
            status,
            hold.label("hold_reason"),
            total_reports.label("total_reports"),
            released_reports.label("released_reports"),
            tests.c.ordered_tests,
            tests.c.released_tests,
            tests.c.canceled_tests,
            reports.c.report_id.label("report_instance_id"),
            selected_report.status.label("lab_report_status"),
            LabReportTemplate.name.label("report_template_name"),
        )
        .select_from(base)
        .join(Patient, and_(Patient.id == base.c.patient_id, ~Patient.is_deleted))
        .outerjoin(
            reports,
            and_(
                reports.c.source == base.c.source,
                reports.c.source_id == base.c.source_id,
            ),
        )
        .outerjoin(tests, tests.c.order_id == base.c.order_id)
        .outerjoin(
            specimens,
            specimens.c.order_id == base.c.order_id,
        )
        .outerjoin(tickets, tickets.c.id == base.c.queue_entry_id)
        .outerjoin(
            selected_report,
            selected_report.id == reports.c.report_id,
        )
        .outerjoin(
            LabReportTemplate, LabReportTemplate.id == selected_report.template_id
        )
        .where(
            *_search_predicate(db, payload, base, visit_services, revisions),
        )
    )
    if payload.from_date:
        stmt = stmt.where(base.c.work_date >= payload.from_date)
    if payload.to_date:
        stmt = stmt.where(base.c.work_date <= payload.to_date)
    return stmt.cte("filtered_lab_work_rows")


def _cursor_hash(payload: LabWorklistSearch, today: date) -> str:
    filters = payload.model_dump(mode="json", exclude={"cursor", "limit"})
    filters["clinic_date"] = today.isoformat()
    encoded = json.dumps(filters, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]


def _encoded_cursor(row, digest: str) -> str:
    raw = json.dumps(
        [digest, row.source, row.source_id], separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decoded_cursor(cursor: str, digest: str) -> tuple[str, int]:
    try:
        actual_digest, source, source_id = json.loads(
            base64.b64decode(cursor, altchars=b"-_", validate=True)
        )
        if (
            actual_digest != digest
            or source not in _SOURCE_TYPES
            or type(source_id) is not int
            or not 0 < source_id <= 2_147_483_647
        ):
            raise ValueError
    except (ValueError, TypeError, UnicodeError) as exc:
        raise InvalidWorklistCursor from exc
    return source, source_id


def _view_predicates(work, now: datetime):
    actionable = ~work.c.status.in_(("ready", "canceled"))
    return {
        "actionable": actionable,
        "today": work.c.work_date == now.date(),
        "overdue": and_(actionable, work.c.due_at < now.astimezone(UTC)),
        "awaiting_specimen": work.c.status == "awaiting_specimen",
        "in_review": work.c.status == "in_review",
        "ready": work.c.status == "ready",
    }


def _count_expressions(views):
    return [
        func.count().filter(predicate).label(name) for name, predicate in views.items()
    ]


def count_lab_worklist(
    db: Session, timezone: ZoneInfo, *, now: datetime | None = None
) -> LabWorklistCounts:
    now = (now or datetime.now(UTC)).astimezone(timezone)
    work = _filtered_work_rows(db, LabWorklistSearch(), now)
    views = _view_predicates(work, now)
    counts = (
        db.execute(select(*_count_expressions(views)).select_from(work))
        .mappings()
        .one()
    )
    return LabWorklistCounts.model_validate(counts)


def _attach_services(db: Session, rows) -> dict:
    visits = {row.visit_id for row in rows if row.source == "visit"}
    orders = {row.order_id for row in rows if row.source == "order"}
    services = defaultdict(list)
    if not visits and not orders:
        return services
    source = lab_visit_services(include_previously_allocated=True).subquery()
    unresolved = (
        unallocated_lab_report_visits().where(Visit.id == source.c.visit_id).exists()
    )
    open_orders = active_lab_orders().subquery()
    order_count = (
        select(func.count())
        .select_from(open_orders)
        .where(
            open_orders.c.visit_id == source.c.visit_id,
        )
        .scalar_subquery()
    )
    can_cancel = and_(LabOrderTest.id.is_(None), ~unresolved, order_count <= 1).label(
        "can_cancel"
    )
    matches = db.execute(
        select(source, LabOrderTest.order_id, LabOrderTest.canceled_at, can_cancel)
        .outerjoin(
            LabOrderTest,
            LabOrderTest.visit_service_id == source.c.visit_service_id,
        )
        .where(
            or_(
                and_(source.c.visit_id.in_(visits), LabOrderTest.id.is_(None)),
                LabOrderTest.order_id.in_(orders),
            )
        )
        .order_by(source.c.visit_service_id)
    ).all()
    for item in matches:
        key = (
            ("order", item.order_id)
            if item.order_id is not None
            else ("visit", item.visit_id)
        )
        services[key].append(
            LabWorklistService(
                id=item.service_id,
                visit_service_id=item.visit_service_id,
                code=normalize_service_code(item.code) if item.code else None,
                name=item.name,
                quantity=item.quantity,
                canceled=item.canceled_at is not None,
                can_cancel=item.can_cancel,
            )
        )
    return services


def _attach_specimens(db: Session, rows) -> dict:
    order_ids = {row.order_id for row in rows if row.order_id is not None}
    specimens = defaultdict(list)
    if order_ids:
        for item in db.execute(
            select(LabSpecimen.order_id, LabSpecimen.id, LabSpecimen.barcode)
            .where(
                LabSpecimen.order_id.in_(order_ids),
            )
            .order_by(LabSpecimen.id)
        ).all():
            specimens[item.order_id].append((item.id, item.barcode))
    return specimens


def _entry_out(
    row, services: list[LabWorklistService], specimens: list[tuple[int, str]]
) -> LabWorklistEntry:
    return LabWorklistEntry(
        id=f"{row.source}:{row.source_id}",
        patient_id=row.patient_id,
        patient_fio=row.patient_fio,
        patient_birth_year=row.birth_date.year if row.birth_date else None,
        visit_id=row.visit_id,
        appointment_id=row.appointment_id,
        order_id=row.order_id,
        queue_entry_id=row.queue_entry_id,
        queue_number=row.queue_number,
        queue_status=row.queue_status,
        appointment_time=row.appointment_time,
        work_date=row.work_date,
        created_at=row.created_at,
        due_at=row.due_at,
        priority=row.priority,
        status=row.status,
        hold_reason=row.hold_reason,
        service_details=services,
        services=[item.name for item in services],
        service_codes=list(dict.fromkeys(item.code for item in services if item.code)),
        report_instance_id=row.report_instance_id,
        report_template_name=row.report_template_name,
        lab_report_status=row.lab_report_status,
        progress=LabWorklistProgress(
            total_reports=row.total_reports,
            released_reports=row.released_reports,
            ordered_tests=row.ordered_tests,
            released_tests=row.released_tests,
            canceled_tests=row.canceled_tests,
        ),
        specimen_ids=[item[0] for item in specimens],
        specimen_barcodes=[item[1] for item in specimens],
    )


def search_lab_worklist(
    db: Session,
    payload: LabWorklistSearch,
    timezone: ZoneInfo,
    *,
    now: datetime | None = None,
) -> LabWorklistPage:
    now = (now or datetime.now(UTC)).astimezone(timezone)
    work = _filtered_work_rows(db, payload, now)
    views = _view_predicates(work, now)
    selected = literal(True) if payload.barcode else views[payload.view]
    counts = (
        select(
            func.count().filter(selected).label("total"),
            *_count_expressions(views),
        )
        .select_from(work)
        .cte("lab_worklist_counts")
    )
    sort_columns = (work.c.work_date, work.c.source, work.c.source_id)
    if payload.sort == "name":
        sort_columns = (work.c.name_sort, *sort_columns)
    descending = payload.sort == "newest"
    ordering = [
        column.desc() if descending else column.asc() for column in sort_columns
    ]
    digest = _cursor_hash(payload, now.date())
    page = select(work).where(selected)
    cursor_valid = literal(True)
    if payload.cursor:
        source, source_id = _decoded_cursor(payload.cursor, digest)
        anchor = (
            select(*sort_columns)
            .where(
                work.c.source == source,
                work.c.source_id == source_id,
            )
            .cte("lab_worklist_cursor")
        )
        cursor_valid = select(1).select_from(anchor).exists()
        current_key = tuple_(*sort_columns)
        anchor_key = tuple_(*(anchor.c[column.key] for column in sort_columns))
        page = page.join(anchor, literal(True)).where(
            current_key < anchor_key if descending else current_key > anchor_key
        )
    bounded = page.order_by(*ordering).limit(payload.limit + 1).subquery()
    page_order = [
        bounded.c[column.key].desc() if descending else bounded.c[column.key].asc()
        for column in sort_columns
    ]
    result = db.execute(
        select(bounded, counts, cursor_valid.label("cursor_valid"))
        .select_from(counts)
        .outerjoin(bounded, literal(True))
        .order_by(*page_order)
    ).all()
    totals = result[0]
    if not totals.cursor_valid:
        raise InvalidWorklistCursor
    rows = [row for row in result[: payload.limit] if row.source_id is not None]
    services = _attach_services(db, rows)
    specimens = _attach_specimens(db, rows)
    entries = [
        _entry_out(row, services[(row.source, row.source_id)], specimens[row.order_id])
        for row in rows
    ]
    return LabWorklistPage(
        entries=entries,
        total=totals.total,
        counts=LabWorklistCounts(**{name: getattr(totals, name) for name in views}),
        next_cursor=_encoded_cursor(rows[-1], digest)
        if len(result) > payload.limit
        else None,
        date=now.date(),
        timezone=timezone.key,
    )
