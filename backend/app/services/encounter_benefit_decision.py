"""Authorize and apply a single benefit to a complete registrar invoice."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import normalize_role_value
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.services.encounter_benefit_net import (
    BenefitQuoteError,
    _read_snapshot,
    quote_from_financial_snapshot,
    require_no_existing_financial_adjustment,
)
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_private_schema,
    _financial_schema,
    lock_financial_group,
)
from app.services.money_input import MoneyInputError, parse_money
from app.services.patient_subject_lock import (
    PatientSubjectLockError,
    lock_patient_subject,
    require_patient_subject_visibility,
)
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
    lock_profile_users,
)

_CATALOG_FUNCTION = "approve_registrar_benefit(integer,integer,integer,bigint,text)"
_UNAVAILABLE = "Подтверждение льготы временно недоступно"
_CONFLICT = "Обращение или право на льготу требует сверки"


class EncounterBenefitDecisionError(ValueError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class EncounterBenefitDecision:
    application_id: int
    invoice_id: int
    gross_total: Decimal
    benefit_total: Decimal
    total_amount: Decimal


def _require_decision_capability(db: Session) -> str:
    _financial_schema(db)
    private = _financial_private_schema(db)
    signature = f"{private}.{_CATALOG_FUNCTION}"
    valid = db.execute(text("""
      SELECT p.prosecdef AND p.prokind='f' AND p.provolatile='v'
        AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype
        AND pg_catalog.cardinality(p.proconfig)=3 AND 'search_path=pg_catalog'=ANY(p.proconfig)
        AND 'row_security=off'=ANY(p.proconfig) AND 'extra_float_digits=3'=ANY(p.proconfig)
        AND p.proowner=n.nspowner AND NOT owner.rolcanlogin AND NOT owner.rolsuper
        AND NOT owner.rolbypassrls AND NOT owner.rolcreaterole AND NOT owner.rolcreatedb AND NOT owner.rolreplication
        AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) acl
          WHERE acl.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
            OR (acl.grantee<>p.proowner AND (acl.privilege_type<>'EXECUTE' OR acl.is_grantable)))
        AND (SELECT count(*)=5 AND COALESCE(bool_and(c.relrowsecurity AND
           NOT pg_catalog.has_any_column_privilege(CURRENT_USER,c.oid,'INSERT,UPDATE') AND
           NOT pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'DELETE,TRUNCATE,TRIGGER')),false)
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace a ON a.oid=c.relnamespace
          WHERE a.nspname=:schema AND c.relkind='r' AND c.relname IN ('encounter_benefit_applications',
            'encounter_benefit_allocations','encounter_benefit_events','encounter_benefit_visit_snapshots',
            'encounter_benefit_quota_anchors'))
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
      WHERE p.oid=pg_catalog.to_regprocedure(:signature)
    """), {"signature": signature, "schema": settings.TRUSTED_DB_SCHEMA}).scalar_one_or_none()
    if valid is not True:
        raise EncounterBenefitDecisionError(503, _UNAVAILABLE)
    return f"{private}.approve_registrar_benefit"


def approve_registrar_benefit(
    db: Session, *, invoice_id: int, assignment_id: int, bearer: ProfileBearerContext,
) -> EncounterBenefitDecision:
    """The entry point owns the final commit and rolls back any error."""
    if (not isinstance(bearer, ProfileBearerContext) or bearer.patient_id is not None
            or type(bearer.user_id) is not int or bearer.user_id <= 0
            or type(bearer.auth_epoch) is not int or bearer.auth_epoch < 0
            or not isinstance(bearer.jti, str) or not bearer.jti
            or type(bearer.expires_at) is not int or bearer.expires_at <= 0):
        raise ProfileBearerInvalid("Bearer session unavailable")
    if any(type(value) is not int or not 1 <= value <= 2147483647 for value in (invoice_id, assignment_id)):
        raise EncounterBenefitDecisionError(422, "Некорректный счёт или назначение льготы")
    if db.get_bind().dialect.name != "postgresql" or db.new or db.dirty or db.deleted:
        raise EncounterBenefitDecisionError(503, _UNAVAILABLE)

    try:
        require_patient_subject_visibility(db)
        function = _require_decision_capability(db)
        actor, _ = lock_profile_users(db, bearer.user_id, bearer.user_id)
        check_profile_bearer(db, actor, bearer)
        if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "superadmin"}:
            raise EncounterBenefitDecisionError(403, "Доступ запрещён")

        invoice = db.get(PaymentInvoice, invoice_id, populate_existing=True)
        if invoice is None or invoice.registrar_encounter_id_snapshot is None:
            raise EncounterBenefitDecisionError(409, _CONFLICT)
        patient_id = invoice.patient_id
        if not lock_patient_subject(db, patient_id):
            raise EncounterBenefitDecisionError(409, _CONFLICT)
        visit_id = (db.query(PaymentInvoiceVisit.visit_id).filter(PaymentInvoiceVisit.invoice_id == invoice_id)
                    .order_by(PaymentInvoiceVisit.visit_id).limit(1).scalar())
        group = lock_financial_group(db, visit_id)
        if (group.encounter.patient_id != patient_id
                or len(group.invoices) != 1 or group.invoices[0].id != invoice_id
                or group.invoices[0].registrar_encounter_id_snapshot != group.encounter.id
                or group.invoices[0].registrar_encounter_generation_snapshot != group.encounter.generation
                or [link.visit_id for link in group.links] != [visit.id for visit in group.visits]):
            raise EncounterBenefitDecisionError(409, _CONFLICT)
        require_no_existing_financial_adjustment(db, visit_id)
        payload = db.execute(text(f"""SELECT {function}(
            CAST(:invoice AS integer),CAST(:assignment AS integer),CAST(:actor AS integer),
            CAST(:epoch AS bigint),CAST(:timezone AS text)
        )"""), {"invoice": invoice_id, "assignment": assignment_id, "actor": actor.id,
                  "epoch": bearer.auth_epoch, "timezone": settings.TIMEZONE}).scalar_one()
        if (not isinstance(payload, dict) or payload.get("invoice_id") != invoice_id
                or type(payload.get("application_id")) is not int or payload["application_id"] <= 0):
            raise EncounterBenefitDecisionError(503, _UNAVAILABLE)
        gross, benefit, total = (parse_money(payload.get(key)) for key in ("gross_total", "benefit_total", "total_amount"))
        if benefit <= 0 or gross - benefit != total:
            raise EncounterBenefitDecisionError(503, _UNAVAILABLE)

        # Prove that existing cashier and checkout readers see the same
        # audited price before returning a result eligible for commit.
        snapshot = _read_snapshot(db, visit_id)
        quote = quote_from_financial_snapshot(snapshot, visit_id=visit_id)
        if not quote.has_benefit:
            raise EncounterBenefitDecisionError(503, _UNAVAILABLE)
        applied = snapshot["applications"][0]
        if (applied["id"] != payload["application_id"]
                or tuple(parse_money(applied.get(key)) for key in ("gross", "discount", "net")) != (gross, benefit, total)):
            raise EncounterBenefitDecisionError(503, _UNAVAILABLE)
        db.expire_all()
        check_bearer_expiry(bearer)
        return EncounterBenefitDecision(payload["application_id"], invoice_id, gross, benefit, total)
    except PatientSubjectLockError as exc:
        raise EncounterBenefitDecisionError(exc.status_code, exc.detail) from None
    except (FinancialFenceError, BenefitQuoteError):
        raise EncounterBenefitDecisionError(409, _CONFLICT) from None
    except MoneyInputError:
        raise EncounterBenefitDecisionError(503, _UNAVAILABLE) from None
    except DBAPIError as exc:
        state = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if state in {"P0001", "23505", "23514", "40P01", "55P03", "40001"}:
            raise EncounterBenefitDecisionError(409, _CONFLICT) from None
        raise EncounterBenefitDecisionError(503, _UNAVAILABLE) from None
