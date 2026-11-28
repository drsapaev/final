"""Worklist totals and timestamped laboratory turnaround cohorts."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, extract, func, select
from sqlalchemy.orm import Session

from app.models.lab import LabReportInstance
from app.models.lab_critical_communication import LabCriticalCommunication
from app.models.lab_specimen import (
    LabSpecimen,
    LabSpecimenAssignment,
    LabSpecimenEvent,
    LabSpecimenRejectionReasonCode,
)
from app.repositories.lab_worklist_repository import count_lab_worklist


def laboratory_metrics(db: Session, timezone: ZoneInfo, *, days: int) -> dict:
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    totals = count_lab_worklist(db, timezone, now=now)
    # Event notes are clinical free text. Categorize only explicit codes;
    # uncategorized historical events contribute to the unknown bucket.
    category = case(
        (
            LabSpecimenEvent.reason_code.in_(tuple(LabSpecimenRejectionReasonCode)),
            LabSpecimenEvent.reason_code,
        ),
        else_="unknown",
    )
    specimen_event_counts = db.execute(
        select(LabSpecimenEvent.action, category, func.count())
        .where(
            LabSpecimenEvent.happened_at >= start,
            LabSpecimenEvent.happened_at < now,
            LabSpecimenEvent.action.in_(("reject", "hold")),
        )
        .group_by(LabSpecimenEvent.action, category)
    ).all()
    rejection_counts = {
        reason: count
        for action, reason, count in specimen_event_counts
        if action == "reject"
    }
    held_count = sum(
        count for action, _, count in specimen_event_counts if action == "hold"
    )

    if db.get_bind().dialect.name == "sqlite":
        # SQLite stores these timestamps as text and cannot subtract them directly.
        seconds = 86_400 * (
            func.julianday(LabReportInstance.finalized_at)
            - func.julianday(LabSpecimen.received_at)
        )
    else:
        seconds = extract("epoch", LabReportInstance.finalized_at - LabSpecimen.received_at)
    sample_count, mean_seconds = db.execute(
        select(func.count(), func.avg(seconds))
        .select_from(LabSpecimenAssignment)
        .join(
            LabReportInstance,
            LabReportInstance.id == LabSpecimenAssignment.report_instance_id,
        )
        .join(LabSpecimen, LabSpecimen.id == LabSpecimenAssignment.specimen_id)
        .where(
            LabReportInstance.supersedes_instance_id.is_(None),
            LabReportInstance.finalized_at >= start,
            LabReportInstance.finalized_at < now,
            LabSpecimen.received_at <= LabReportInstance.finalized_at,
        )
    ).one()

    corrections = db.scalar(
        select(func.count())
        .select_from(LabReportInstance)
        .where(
            LabReportInstance.supersedes_instance_id.is_not(None),
            LabReportInstance.finalized_at >= start,
            LabReportInstance.finalized_at < now,
        )
    )
    communications_open = db.scalar(
        select(func.count())
        .select_from(LabCriticalCommunication)
        .where(LabCriticalCommunication.state.notin_(("acknowledged", "superseded")))
    )
    return {
        "from_at": start,
        "until_at": now,
        "actionable": totals.actionable,
        "overdue": totals.overdue,
        "rejected_samples": sum(rejection_counts.values()),
        "rejected_samples_by_reason": rejection_counts,
        "held_samples": held_count,
        "turnaround_pairs": sample_count,
        "average_turnaround_minutes": round(float(mean_seconds) / 60, 1)
        if mean_seconds is not None
        else None,
        "released_corrections": corrections,
        "communications_open": communications_open,
    }
