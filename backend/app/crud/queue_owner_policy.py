"""QD-2E (RQ-15.b): the fail-closed queue-owner policy (D-08).

ADR-001 "Stage E ``general`` decision" (owner decision D-08, 2026-09-12):
``general`` is retired as a routing destination — it is not a real
standalone queue, a bookable specialty or an active ``QueueResource``.
The string survives only as the incomplete-Doctor onboarding sentinel.

The terminal routing rule this module encodes (the single SSOT every
runtime owner-resolution surface shares from stage E on):

- a registry tag (an ACTIVE ``queue_resources`` row, exact tag) routes
  on the resource axis (the QD-2C switch) — no doctor needed;
- an explicit real Doctor routes on the doctor axis: the visit's doctor,
  or the single doctor carried by the tag's active services;
- anything else is a **configuration error**. There is no
  ``general_resource`` fallback, no arbitrary-active-doctor fallback and
  no inference from service names or codes (D-08: the operator map is
  the only source of retag/assign/disable decisions).

``QueueOwnerConfigurationError`` subclasses ``ValueError`` on purpose:
the existing endpoint handlers already surface ``ValueError`` as a
4xx with the message (the registrar cart precedent), so a
configuration error reaches the operator instead of a bare 500, while
tests can pin the dedicated type.

CRUD layer (pure model lookups): safe to import from services,
repositories, endpoints and the crud layer itself — no
context-boundary edge (the QD-2C ``queue_resource_routing`` precedent).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.service import Service


class QueueOwnerConfigurationError(ValueError):
    """A queue surface has no explicit owner — a configuration error.

    Raised when a queue-bearing operation (booking, batch create,
    morning pre-create/assignment, visit confirmation) cannot resolve
    an owner for a tag: no ACTIVE ``queue_resources`` row, no explicit
    Doctor on the visit or the tag's services. Stage E removed the
    ``general_resource`` universal fallback (D-08) — the fix is an
    operator decision (assign a doctor, retag to an active resource or
    disable the service), never a runtime guess.
    """


def owner_configuration_error(
    *, queue_tag: str | None, detail: str = ""
) -> QueueOwnerConfigurationError:
    """Build the uniform fail-closed error for a queue surface.

    The message names the surface and the three operator resolutions —
    the same vocabulary the operator map (RQ-15.b) uses, so the desk
    operator reading a 4xx detail sees exactly what to decide.
    """
    tag_part = f"queue_tag={queue_tag!r}" if queue_tag else "queue_tag is NULL"
    suffix = f"; {detail}" if detail else ""
    return QueueOwnerConfigurationError(
        f"Конфигурационная ошибка владельца очереди ({tag_part}): "
        "нет активной строки queue_resources и нет явного врача — "
        "автоматический fallback на general_resource запрещён (D-08). "
        "Назначьте врача, переключите queue_tag на активный ресурс или "
        "отключите услугу (operator map RQ-15.b)" + suffix
    )


def single_active_service_doctor(db: Session, queue_tag: str) -> int | None:
    """The single distinct doctor carried by the tag's ACTIVE services.

    Returns the doctor id only when exactly one distinct non-NULL
    ``Service.doctor_id`` exists among the tag's active services — the
    explicit-owner shortcut the morning pre-create and the assignment
    paths use for non-registry doctor specialties (K01/K11 → the
    cardiologist after the RQ-15.b map application). ``None`` for zero
    owners (a fail-closed surface) and for two or more owners (an
    explicit doctor must be chosen per booking — the PR-26 per-doctor
    queue contract, never a migration/runtime guess).
    """
    rows = (
        db.query(Service.doctor_id)
        .filter(
            Service.active.is_(True),
            Service.queue_tag == queue_tag,
            Service.doctor_id.isnot(None),
        )
        .distinct()
        .all()
    )
    doctor_ids = [int(row[0]) for row in rows if row[0] is not None]
    if len(doctor_ids) == 1:
        return doctor_ids[0]
    return None


def is_internal_resource_doctor(doctor) -> bool:
    """True when the Doctor row belongs to an internal queue-resource
    account (the 0056/0057 'Resource' role — the lab/ecg/general
    synthetics and any future resource account).

    QD-2E (RQ-15.b): such accounts are never QUEUE OWNERS. The runtime
    resolvers exclude them from every owner-resolution chain — the
    specialty-matching fallback included — so a synthetic cannot be
    reached through its specialty either (D-08: no route onto the
    synthetics, whatever the path). Role-based (no username list in
    runtime code — the ADR gate-5 vocabulary ruling).
    """
    from app.core.roles import is_internal_only_role_spelling

    user = getattr(doctor, "user", None)
    if user is None:
        return False
    role = getattr(user, "role", None)
    if role is None:
        return False
    return is_internal_only_role_spelling(role)
