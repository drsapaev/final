"""Small read helpers for the lab_reporting mixins."""


def baseline_templates_present(repository, codes: list[str]) -> bool:
    """True iff at least one seeded baseline template row still exists.

    ONE lightweight query (the list_templates-by-codes path carries heavy
    joinedload versions); used by the 404 self-heal gate so an arbitrary
    unknown id fails fast without re-running the seeders.
    """
    from sqlalchemy import select as _select

    from app.models.lab import LabReportTemplate  # model lives in app.models.lab (Codex P1)

    stmt = _select(LabReportTemplate.id).where(
        LabReportTemplate.code.in_(codes)
    ).limit(1)
    return repository.db.execute(stmt).scalars().first() is not None
