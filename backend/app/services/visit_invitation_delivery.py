"""Stage and claim a subject-bound visit invitation without storing its bearer.

Claim is deliberately conservative: it commits ``unknown`` before any network
I/O. A crash before the call and a timeout after provider acceptance are
indistinguishable, so neither can be retried automatically.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import func as sa_func
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import normalize_role_value
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.user_profile import UserNotificationSettings, UserPreferences
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import (
    VisitInvitationApprovalRecovery,
    VisitInvitationDelivery,
    VisitInvitationIssuerAuth,
    VisitInvitationPriceApprovalAuth,
)
from app.services.authorization.staff import staff_authorization_service
from app.services.money_input import MoneyInputError, parse_money
from app.services.profile_contact_security import (
    ProfileBearerContext,
    ProfileBearerInvalid,
    check_profile_bearer,
)

_INVITATION_GUARD_BODY_SHA256 = "a91059a82c5d12bd1ac1ad98c7a8c66032bb7531456e62649fe2609678366ce7"


class InvitationContextChanged(ValueError):
    """The intended subject or confirmation capability is no longer current."""


class InvitationRuntimeUnavailable(RuntimeError):
    """The trusted database schema or runtime RLS boundary is unavailable."""


def _jti_fernet() -> Fernet:
    secret = settings.SECRET_KEY
    if not isinstance(secret, str) or not secret:
        raise InvitationRuntimeUnavailable("Invitation authorization unavailable")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"clinic.visit-invitation.issuer-jti.v1").derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def _issuer_payload(row: VisitInvitationIssuerAuth, *, jti: str) -> dict:
    return {
        "v": 1, "delivery_id": row.delivery_id, "actor": row.actor_user_id_snapshot,
        "auth_epoch": row.actor_auth_epoch, "requester": row.requester_type,
        "doctor": row.doctor_id_snapshot, "doctor_generation": row.doctor_generation,
        "expires": row.expires_at, "jti": jti,
    }


def _recover_jti(row: VisitInvitationIssuerAuth) -> str | None:
    if row.cipher_version != 1:
        return None
    try:
        decoded = _jti_fernet().decrypt(row.jti_ciphertext.encode("ascii"))
        payload = json.loads(decoded)
        jti = payload.get("jti") if isinstance(payload, dict) else None
        if not isinstance(jti, str) or not jti or len(jti) > 36:
            return None
        return jti if payload == _issuer_payload(row, jti=jti) else None
    except (InvalidToken, UnicodeError, ValueError, TypeError, InvitationRuntimeUnavailable):
        return None


def _price_approval_payload(row: VisitInvitationPriceApprovalAuth, *, jti: str) -> dict:
    return {
        "v": 1, "kind": "price_approval", "delivery_id": row.delivery_id,
        "actor": row.actor_user_id_snapshot, "auth_epoch": row.actor_auth_epoch,
        "override": row.override_id_snapshot, "line": row.line_id_snapshot,
        "line_generation": row.line_generation, "unit_price": format(row.unit_price, ".2f"),
        "quantity": row.quantity, "expires": row.expires_at, "jti": jti,
    }


def _recover_approval_jti(row: VisitInvitationPriceApprovalAuth) -> str | None:
    if row.cipher_version != 1:
        return None
    try:
        payload = json.loads(_jti_fernet().decrypt(row.jti_ciphertext.encode("ascii")))
        jti = payload.get("jti") if isinstance(payload, dict) else None
        if not isinstance(jti, str) or not jti or len(jti) > 36:
            return None
        return jti if payload == _price_approval_payload(row, jti=jti) else None
    except (InvalidToken, UnicodeError, ValueError, TypeError, InvitationRuntimeUnavailable):
        return None


def _load_issuer(db: Session, delivery_id: int):
    original = db.query(VisitInvitationIssuerAuth).filter(VisitInvitationIssuerAuth.delivery_id == delivery_id).first()
    approval = db.query(VisitInvitationPriceApprovalAuth).filter(VisitInvitationPriceApprovalAuth.delivery_id == delivery_id).first()
    if (original is None) == (approval is None):
        return None
    return original if original is not None else approval


def _lock_and_check_actor(
    db: Session, bearer: ProfileBearerContext, requester_type: str,
    doctor_id: int | None, doctor_generation: int | None, visit: Visit | None = None,
) -> bool:
    actor = db.query(User).filter(User.id == bearer.user_id).populate_existing().with_for_update(nowait=True).first()
    if actor is None:
        return False
    try:
        check_profile_bearer(db, actor, bearer)
    except ProfileBearerInvalid:
        return False
    role = normalize_role_value(actor.role)
    allowed_roles = {"admin", "doctor", "registrar", "cashier", "cardio", "cardiology", "derma", "dentist"}
    if not actor.is_superuser and role not in allowed_roles:
        return False
    if requester_type == "admin":
        if not staff_authorization_service.has_permission(actor, "users:manage"):
            return False
    elif requester_type != "doctor" or doctor_id is None:
        return False
    if doctor_id is not None:
        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).populate_existing().with_for_update(nowait=True).first()
        if (doctor is None or not doctor.active or doctor.user_id != actor.id
            or doctor.price_owner_generation != doctor_generation
            or (visit is not None and visit.doctor_id != doctor.id)):
            return False
    return bearer.expires_at is not None and bearer.expires_at > time.time()


def _lock_and_check_issuer(db: Session, row: VisitInvitationIssuerAuth | VisitInvitationPriceApprovalAuth, visit: Visit | None = None) -> bool:
    """Revalidate exact issuer session and doctor identity under locks."""
    if isinstance(row, VisitInvitationPriceApprovalAuth):
        if (row.actor_user_id is None or row.actor_user_id != row.actor_user_id_snapshot
            or row.override_id != row.override_id_snapshot or row.line_id != row.line_id_snapshot):
            return False
        actor = db.query(User).filter(User.id == row.actor_user_id).populate_existing().with_for_update(nowait=True).first()
        jti = _recover_approval_jti(row)
        if actor is None or jti is None:
            return False
        bearer = ProfileBearerContext(actor.id, row.actor_auth_epoch, jti, row.expires_at, None)
        try:
            check_profile_bearer(db, actor, bearer)
        except ProfileBearerInvalid:
            return False
        if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "superadmin", "registrar"}:
            return False
        if row.expires_at <= time.time():
            return False
        if visit is None:
            return True
        override = db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id == row.override_id).populate_existing().with_for_update(nowait=True).first()
        line = db.query(VisitService).filter(VisitService.id == row.line_id).populate_existing().with_for_update(nowait=True).first()
        return bool(override is not None and line is not None and override.status == "approved"
                    and override.approved_by == actor.id and override.visit_id == visit.id
                    and override.target_scope == "visit_service" and override.target_visit_service_id == line.id
                    and override.service_id == line.service_id and line.visit_id == visit.id
                    and line.price_line_generation == row.line_generation
                    and line.price == row.unit_price and line.qty == row.quantity)
    if (row.actor_user_id is None or row.actor_user_id != row.actor_user_id_snapshot
        or (row.doctor_id_snapshot is not None and row.doctor_id != row.doctor_id_snapshot)):
        return False
    jti = _recover_jti(row)
    if jti is None:
        return False
    bearer = ProfileBearerContext(row.actor_user_id, row.actor_auth_epoch, jti, row.expires_at, None)
    return _lock_and_check_actor(db, bearer, row.requester_type, row.doctor_id_snapshot,
                                 row.doctor_generation, visit)


def pin_invitation_runtime(db: Session) -> None:
    """Validate the deployment anchor and table RLS before any ORM query.

    Operators must drain traffic for schema/role/ACL changes. A table lock
    keeps the verified policies stable until this transaction ends.
    """
    from app.services.context_facades.patient_facade import (
        PatientSubjectLockError,
        require_patient_subject_visibility,
    )

    dialect = db.get_bind().dialect
    # The issuer/JTI and the subject must be checked in the same verified
    # application namespace as the invitation tables on every transaction.
    if dialect.name == "postgresql" and (
        not settings.TRUSTED_DB_SCHEMA or settings.TRUSTED_DB_SCHEMA != settings.INVITATION_DB_SCHEMA
        or not settings.TRUSTED_DB_SCHEMA_OWNER
        or settings.TRUSTED_DB_SCHEMA_OWNER != settings.INVITATION_DB_SCHEMA_OWNER
    ):
        raise InvitationRuntimeUnavailable("Invitation storage unavailable")
    try:
        require_patient_subject_visibility(db)
    except PatientSubjectLockError:
        raise InvitationRuntimeUnavailable("Invitation storage unavailable") from None
    _pin_invitation_storage(db)


def _pin_invitation_storage(db: Session) -> None:
    """Verify invitation storage ACLs; callers must also pin subject auth."""
    dialect = db.get_bind().dialect
    if dialect.name == "sqlite":
        return
    if dialect.name != "postgresql":
        raise InvitationRuntimeUnavailable("Invitation storage unavailable")
    schema, owner, table_owner = (settings.INVITATION_DB_SCHEMA, settings.INVITATION_DB_SCHEMA_OWNER,
                                  settings.INVITATION_DB_TABLE_OWNER)
    if any(not isinstance(value, str) or not value or "\x00" in value or len(value.encode("utf-8")) > 63
           for value in (schema, owner, table_owner)):
        raise InvitationRuntimeUnavailable("Invitation storage unavailable")
    if ((settings.DOCTOR_PRICE_DB_SCHEMA is not None and settings.DOCTOR_PRICE_DB_SCHEMA != schema)
        or (settings.DOCTOR_PRICE_DB_SCHEMA_OWNER is not None and settings.DOCTOR_PRICE_DB_SCHEMA_OWNER != owner)):
        raise InvitationRuntimeUnavailable("Invitation storage unavailable")
    try:
        metadata = db.execute(text("""
          SELECT n.oid AS schema_oid,n.nspowner,o.rolname AS owner_name,
                 o.rolsuper AS owner_super,o.rolcanlogin AS owner_login,
                 a.oid AS actor_oid,a.rolcanlogin,a.rolsuper,a.rolbypassrls,
                 a.rolcreaterole,a.rolcreatedb,a.rolreplication,
                 c.relowner AS table_owner_oid,t.rolsuper AS table_owner_super,t.rolcanlogin AS table_owner_login
          FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles o ON o.oid=n.nspowner
          JOIN pg_catalog.pg_class c ON c.relnamespace=n.oid AND c.relname='visit_invitation_deliveries' AND c.relkind='r'
          JOIN pg_catalog.pg_roles t ON t.oid=c.relowner
          JOIN pg_catalog.pg_roles a ON a.rolname=CURRENT_USER
          WHERE n.nspname=:schema AND o.rolname=:owner AND t.rolname=:table_owner
        """), {"schema": schema, "owner": owner, "table_owner": table_owner}).mappings().first()
        if (metadata is None or schema in {"pg_catalog", "information_schema"}
            or not metadata["rolcanlogin"] or any(metadata[key] for key in
                ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))
            or (not metadata["owner_super"] and metadata["owner_login"])
            or (not metadata["table_owner_super"] and metadata["table_owner_login"])):
            raise InvitationRuntimeUnavailable("Invitation storage unavailable")
        safe = db.execute(text("""
          SELECT NOT pg_catalog.has_schema_privilege(:actor,:schema_oid,'CREATE')
            AND NOT pg_catalog.pg_has_role(:actor,:owner_oid,'MEMBER')
            AND NOT pg_catalog.pg_has_role(:actor,:table_owner_oid,'MEMBER')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
              LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE n.oid=:schema_oid AND a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid NOT IN (:owner_oid,:table_owner_oid)
              AND (pg_catalog.pg_has_role(r.oid,:owner_oid,'MEMBER') OR pg_catalog.pg_has_role(r.oid,:table_owner_oid,'MEMBER')))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE NOT r.rolsuper AND r.oid<>:actor
              AND pg_catalog.pg_has_role(r.oid,:actor,'MEMBER'))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
              WHERE (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
                AND pg_catalog.pg_has_role(:actor,r.oid,'MEMBER'))
        """), {"actor": metadata["actor_oid"], "owner_oid": metadata["nspowner"],
                "table_owner_oid": metadata["table_owner_oid"], "schema_oid": metadata["schema_oid"]}).scalar_one()
        if safe is not True:
            raise InvitationRuntimeUnavailable("Invitation storage unavailable")
        quoted = dialect.identifier_preparer.quote_schema(schema)
        db.execute(text("SELECT pg_catalog.set_config('search_path', :path, true)"),
                   {"path": f"pg_catalog, {quoted}, pg_temp"})
        table = f"{quoted}.visit_invitation_deliveries"
        db.execute(text(f"LOCK TABLE {table} IN ACCESS SHARE MODE"))
        valid = db.execute(text("""
          SELECT c.relrowsecurity AND c.relowner=:owner_oid AND c.relkind='r'
            AND pg_catalog.to_regclass('visit_invitation_deliveries')=c.oid
            AND pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT')
            AND pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'INSERT')
            AND pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'UPDATE')
            AND NOT pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'DELETE,TRUNCATE,REFERENCES,TRIGGER')
            AND NOT pg_catalog.has_any_column_privilege(CURRENT_USER,c.oid,'REFERENCES')
            AND pg_catalog.has_sequence_privilege(CURRENT_USER,pg_catalog.pg_get_serial_sequence(:table,'id'),'USAGE')
            AND NOT pg_catalog.has_sequence_privilege(CURRENT_USER,pg_catalog.pg_get_serial_sequence(:table,'id'),'UPDATE')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x
              WHERE x.grantee NOT IN (c.relowner,:actor) OR (x.grantee=:actor AND x.is_grantable))
            AND (SELECT pg_catalog.count(*) FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid)=3
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
              AND p.polname='invitation_backend_select' AND p.polcmd='r' AND p.polpermissive
              AND p.polroles=ARRAY[:actor]::oid[] AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true' AND p.polwithcheck IS NULL)
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
              AND p.polname='invitation_backend_insert' AND p.polcmd='a' AND p.polpermissive
              AND p.polroles=ARRAY[:actor]::oid[] AND p.polqual IS NULL
              AND pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)=:insert_expression)
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
              AND p.polname='invitation_backend_update' AND p.polcmd='w' AND p.polpermissive
              AND p.polroles=ARRAY[:actor]::oid[] AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
              AND pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)='true')
          FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(:table)
        """), {"table": table, "owner_oid": metadata["table_owner_oid"], "actor": metadata["actor_oid"],
                "insert_expression": "(((state)::text = 'pending'::text) AND (dispatch_nonce_digest IS NULL))"}).scalar_one_or_none()
        if valid is not True:
            raise InvitationRuntimeUnavailable("Invitation storage unavailable")
        trigger = db.execute(text("""
          SELECT t.tgenabled,t.tgtype,t.tgqual IS NULL AS no_condition,
                 t.tgoldtable IS NULL AND t.tgnewtable IS NULL AS no_transition,
                 p.proowner,p.prosecdef,p.proconfig,p.prosrc,p.pronargs,
                 p.prorettype='pg_catalog.trigger'::pg_catalog.regtype AS returns_trigger,
                 l.lanname,n.nspname
          FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
          JOIN pg_catalog.pg_language l ON l.oid=p.prolang
          JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
          WHERE t.tgrelid=pg_catalog.to_regclass(:table)
            AND t.tgname='trg_protect_visit_invitation' AND NOT t.tgisinternal
        """), {"table": table}).mappings().first()
        if (trigger is None or trigger["tgenabled"] != "O" or trigger["tgtype"] != 27
            or not trigger["no_condition"] or not trigger["no_transition"]
            or trigger["proowner"] != metadata["table_owner_oid"] or trigger["prosecdef"]
            or trigger["proconfig"] != ["search_path=pg_catalog"] or trigger["pronargs"] != 0
            or not trigger["returns_trigger"] or trigger["lanname"] != "plpgsql" or trigger["nspname"] != schema
            or not isinstance(trigger["prosrc"], str)
            or hashlib.sha256(trigger["prosrc"].strip().encode("utf-8")).hexdigest() != _INVITATION_GUARD_BODY_SHA256):
            raise InvitationRuntimeUnavailable("Invitation storage unavailable")
        auth_table = f"{quoted}.visit_invitation_issuer_auth"
        db.execute(text(f"LOCK TABLE {auth_table} IN ACCESS SHARE MODE"))
        valid_auth = db.execute(text("""
          SELECT c.relrowsecurity AND c.relowner=:owner_oid AND c.relkind='r'
            AND pg_catalog.to_regclass('visit_invitation_issuer_auth')=c.oid
            AND pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT')
            AND pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'INSERT')
            AND NOT pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            AND NOT pg_catalog.has_any_column_privilege(CURRENT_USER,c.oid,'UPDATE,REFERENCES')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x
              WHERE x.grantee NOT IN (c.relowner,:actor) OR (x.grantee=:actor AND x.is_grantable))
            AND (SELECT pg_catalog.count(*) FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid)=2
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
              AND p.polname='invitation_issuer_backend_select' AND p.polcmd='r' AND p.polpermissive
              AND p.polroles=ARRAY[:actor]::oid[] AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true' AND p.polwithcheck IS NULL)
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
              AND p.polname='invitation_issuer_backend_insert' AND p.polcmd='a' AND p.polpermissive
              AND p.polroles=ARRAY[:actor]::oid[] AND p.polqual IS NULL AND pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)='true')
          FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(:table)
        """), {"table": auth_table, "owner_oid": metadata["table_owner_oid"], "actor": metadata["actor_oid"]}).scalar_one_or_none()
        if valid_auth is not True:
            raise InvitationRuntimeUnavailable("Invitation storage unavailable")
        for relation_name, policy_prefix, can_update in (
            ("visit_invitation_price_approval_auth", "invitation_price", False),
            ("visit_invitation_approval_recoveries", "invitation_recovery", True),
        ):
            relation = f"{quoted}.{relation_name}"
            db.execute(text(f"LOCK TABLE {relation} IN ACCESS SHARE MODE"))
            rights = db.execute(text("""
              SELECT c.oid,c.relowner,c.relrowsecurity,c.relkind,
                pg_catalog.to_regclass(:unqualified)=c.oid AS resolved,
                pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT') AS can_select,
                pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'INSERT') AS can_insert,
                pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'UPDATE') AS can_update,
                pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'DELETE,TRUNCATE,REFERENCES,TRIGGER') AS dangerous,
                pg_catalog.has_any_column_privilege(CURRENT_USER,c.oid,'REFERENCES') AS column_danger,
                NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x
                  WHERE x.grantee NOT IN (c.relowner,:actor) OR (x.grantee=:actor AND x.is_grantable)) AS acl_safe
              FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(:table)
            """), {"table": relation, "unqualified": relation_name, "actor": metadata["actor_oid"]}).mappings().first()
            if (rights is None or rights["relowner"] != metadata["table_owner_oid"] or not rights["relrowsecurity"]
                or rights["relkind"] != "r" or not rights["resolved"] or not rights["can_select"] or not rights["can_insert"]
                or rights["can_update"] != can_update or rights["dangerous"] or rights["column_danger"] or not rights["acl_safe"]):
                raise InvitationRuntimeUnavailable("Invitation storage unavailable")
            if not can_update and db.execute(text("SELECT pg_catalog.has_any_column_privilege(CURRENT_USER,:oid,'UPDATE')"),
                                             {"oid": rights["oid"]}).scalar_one():
                raise InvitationRuntimeUnavailable("Invitation storage unavailable")
            policies = db.execute(text("""
              SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                     pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expr,
                     pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expr
              FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            """), {"oid": rights["oid"]}).mappings().all()
            expected_policies = {
                f"{policy_prefix}_select": ("r", "true", None),
                f"{policy_prefix}_insert": ("a", None, "((state)::text = 'pending'::text)" if can_update else "true"),
            }
            if can_update:
                expected_policies[f"{policy_prefix}_update"] = ("w", "true", "true")
            if ({p["polname"] for p in policies} != set(expected_policies)
                or any(not p["polpermissive"] or p["polroles"] != [metadata["actor_oid"]]
                       or (p["polcmd"], p["using_expr"], p["check_expr"]) != expected_policies[p["polname"]]
                       for p in policies)):
                raise InvitationRuntimeUnavailable("Invitation storage unavailable")
            if can_update:
                sequence_ok = db.execute(text("""
                  SELECT pg_catalog.has_sequence_privilege(CURRENT_USER,pg_catalog.pg_get_serial_sequence(:table,'id'),'USAGE')
                    AND NOT pg_catalog.has_sequence_privilege(CURRENT_USER,pg_catalog.pg_get_serial_sequence(:table,'id'),'UPDATE')
                """), {"table": relation}).scalar_one()
                if sequence_ok is not True:
                    raise InvitationRuntimeUnavailable("Invitation storage unavailable")
    except SQLAlchemyError as exc:
        raise InvitationRuntimeUnavailable("Invitation storage unavailable") from exc


@dataclass(frozen=True)
class ClaimedInvitation:
    delivery_id: int
    patient_id: int
    visit_id: int
    owner_generation: int
    context_epoch: int
    channel: str
    telegram_link_id: int | None
    telegram_link_epoch: int | None
    token: str = field(repr=False)
    dispatch_nonce: str = field(repr=False)


def _cancel_pending(db: Session, delivery_id: int) -> None:
    row = db.query(VisitInvitationDelivery).filter(VisitInvitationDelivery.id == delivery_id).with_for_update().first()
    if row is not None and row.state == "pending":
        row.state = "cancelled"
        row.updated_at = datetime.now(UTC)
        db.commit()
    else:
        db.rollback()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _recovery_matches_token(recovery: VisitInvitationApprovalRecovery, visit: Visit) -> bool:
    current = _digest(visit.confirmation_token) if visit.confirmation_token else None
    if current is None or recovery.previous_token_digest is None:
        return current is None and recovery.previous_token_digest is None
    return hmac.compare_digest(current, recovery.previous_token_digest)


def _valid_visit(visit: Visit, patient: Patient) -> bool:
    expires = visit.confirmation_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return bool(
        not patient.is_deleted and patient.notification_owner_generation > 0
        and visit.patient_id == patient.id and visit.status == "pending_confirmation"
        and visit.confirmation_context_epoch > 0 and visit.confirmation_token
        and expires is not None and expires > datetime.now(UTC)
    )


def _lock_invitation_patient(db: Session, patient_id: int) -> Patient | None:
    """Lock the active subject without granting the backend Patient UPDATE."""
    from app.services.context_facades.patient_facade import (
        PatientSubjectLockError,
        lock_patient_subject,
    )

    try:
        if not lock_patient_subject(db, patient_id):
            return None
    except PatientSubjectLockError:
        raise InvitationRuntimeUnavailable("Invitation storage unavailable") from None
    return db.query(Patient).filter(Patient.id == patient_id).populate_existing().first()


def _lock_verified_telegram_link(
    db: Session, patient: Patient, *,
    expected_link: tuple[int | None, int | None] | None = None, nowait: bool = False,
) -> TelegramUser | None:
    links = db.query(TelegramUser).filter(
        TelegramUser.patient_id == patient.id, TelegramUser.chat_id > 0,
        TelegramUser.active.is_(True), TelegramUser.blocked.is_(False),
        TelegramUser.notifications_enabled.is_(True), TelegramUser.appointment_reminders.is_(True),
        TelegramUser.patient_link_epoch > 0,
    )
    if expected_link is not None:
        link_id, link_epoch = expected_link
        links = links.filter(TelegramUser.id == link_id, TelegramUser.patient_link_epoch == link_epoch)
    locked = links.order_by(TelegramUser.id.desc()).populate_existing().with_for_update(nowait=nowait).all()
    # A historical link is eligible only after proof for this patient generation.
    return next((link for link in locked if getattr(link, "patient_owner_generation_snapshot", None)
                 == patient.notification_owner_generation), None)


def _has_unresolved_invitation(db: Session, visit_id: int) -> bool:
    """Check every visible attempt while the caller holds its Visit lock.

    The invitation runtime preflight proves full table visibility. Unknown
    provider outcomes remain unresolved even when their original token or
    patient context changed; rotating a token cannot prove non-delivery.
    """
    return db.query(VisitInvitationDelivery.id).filter(
        VisitInvitationDelivery.visit_id_snapshot == visit_id,
        VisitInvitationDelivery.state.in_(("pending", "unknown")),
    ).first() is not None


def stage_visit_invitation(
    db: Session, *, patient_id: int, visit_id: int, channel: str,
    issuer_actor_id: int | None = None, issuer_key_digest: str | None = None,
    issuer_fingerprint: str | None = None, require_deliverable: bool = False,
    bearer: ProfileBearerContext | None = None, requester_type: str | None = None,
    doctor_id: int | None = None, doctor_generation: int | None = None,
) -> int | None:
    """Stage in the caller's visit transaction; caller must not commit early.

    Acquire Patient before Visit, then the selected link. Caller must already
    obey that ordering, including any earlier locks in its transaction.
    """
    if channel not in {"auto", "telegram", "pwa", "phone"}:
        raise InvitationContextChanged("Unsupported invitation channel")
    issuer = (issuer_actor_id, issuer_key_digest, issuer_fingerprint)
    if any(value is not None for value in issuer) and not (
        isinstance(issuer_actor_id, int) and issuer_actor_id > 0
        and isinstance(issuer_key_digest, str) and len(issuer_key_digest) == 64
        and isinstance(issuer_fingerprint, str) and len(issuer_fingerprint) == 64
    ):
        raise InvitationContextChanged("Invalid invitation issuer context")
    pin_invitation_runtime(db)
    if (bearer is None or bearer.patient_id is not None or not isinstance(bearer.jti, str)
        or not bearer.jti or len(bearer.jti) > 36 or bearer.expires_at is None
        or bearer.expires_at <= time.time()):
        if require_deliverable:
            raise InvitationContextChanged("Issuer session cannot authorize delivery")
        return None
    if ((doctor_id is None) != (doctor_generation is None)
        or requester_type not in {"admin", "doctor"}
        or (issuer_actor_id is not None and issuer_actor_id != bearer.user_id)
        or not _lock_and_check_actor(db, bearer, requester_type, doctor_id, doctor_generation)):
        raise InvitationContextChanged("Issuer authorization changed")
    patient = _lock_invitation_patient(db, patient_id)
    visit = db.query(Visit).filter(Visit.id == visit_id).populate_existing().with_for_update().first()
    if patient is None or visit is None or not _valid_visit(visit, patient):
        raise InvitationContextChanged("Invitation context changed")
    if not _lock_and_check_actor(db, bearer, requester_type, doctor_id, doctor_generation, visit):
        raise InvitationContextChanged("Issuer authorization changed")
    if _has_unresolved_invitation(db, visit.id):
        raise InvitationContextChanged("An invitation attempt is unresolved")
    link = None
    if channel in {"auto", "telegram"}:
        link = _lock_verified_telegram_link(db, patient)
    if channel == "auto":
        channel = "telegram" if link else ("pwa" if patient.phone and patient.phone.startswith("+998") else "phone")
    if channel == "telegram" and link is None:
        if require_deliverable:
            raise InvitationContextChanged("Active Telegram link unavailable")
        return None
    if channel == "pwa" and not patient.phone:
        if require_deliverable:
            raise InvitationContextChanged("SMS contact unavailable")
        return None
    if require_deliverable and channel == "pwa" and patient.user_id is not None:
        # Reissue callers acquire actor and subject users before Patient. NOWAIT
        # also prevents an inverted legacy writer from deadlocking this path.
        subject_user = db.query(User).filter(User.id == patient.user_id).populate_existing().with_for_update(nowait=True).first()
        preferences = db.query(UserPreferences).filter(UserPreferences.user_id == patient.user_id).with_for_update(nowait=True).first()
        notification_settings = db.query(UserNotificationSettings).filter(UserNotificationSettings.user_id == patient.user_id).with_for_update(nowait=True).first()
        if (subject_user is None or not subject_user.is_active
            or (preferences is not None and preferences.sms_notifications is False)
            or (notification_settings is not None and notification_settings.sms_appointment_confirmation is False)):
            raise InvitationContextChanged("SMS delivery is unavailable")
    if require_deliverable and channel == "phone":
        registrar = db.query(User.id).filter(User.is_active.is_(True),
                    sa_func.lower(User.role) == "registrar").with_for_update(nowait=True).first()
        if registrar is None:
            raise InvitationContextChanged("Registrar task unavailable")
    row = VisitInvitationDelivery(
        visit_id=visit.id, visit_id_snapshot=visit.id,
        patient_id=patient.id, patient_id_snapshot=patient.id,
        owner_generation=patient.notification_owner_generation,
        context_epoch=visit.confirmation_context_epoch,
        token_digest=_digest(visit.confirmation_token), channel=channel,
        telegram_link_id=link.id if channel == "telegram" else None,
        telegram_link_epoch=link.patient_link_epoch if channel == "telegram" else None,
        issuer_actor_id=issuer_actor_id, issuer_key_digest=issuer_key_digest,
        issuer_fingerprint=issuer_fingerprint,
        state="pending",
    )
    db.add(row)
    db.flush()
    auth = VisitInvitationIssuerAuth(
        delivery_id=row.id, actor_user_id=bearer.user_id,
        actor_user_id_snapshot=bearer.user_id, actor_auth_epoch=bearer.auth_epoch,
        requester_type=requester_type, doctor_id=doctor_id, doctor_id_snapshot=doctor_id,
        doctor_generation=doctor_generation, expires_at=bearer.expires_at,
        cipher_version=1, jti_ciphertext="",
    )
    plain = json.dumps(_issuer_payload(auth, jti=bearer.jti), sort_keys=True, separators=(",", ":")).encode("utf-8")
    auth.jti_ciphertext = _jti_fernet().encrypt(plain).decode("ascii")
    db.add(auth)
    db.flush()
    return row.id


def _check_approved_line(db: Session, *, override: DoctorPriceOverride, actor: User,
                         bearer: ProfileBearerContext, patient: Patient, visit: Visit) -> VisitService:
    if (actor.id != bearer.user_id or bearer.patient_id is not None or not bearer.jti
        or len(bearer.jti) > 36 or bearer.expires_at is None or bearer.expires_at <= time.time()):
        raise InvitationContextChanged("Approval session unavailable")
    locked_actor = db.query(User).filter(User.id == actor.id).populate_existing().with_for_update(nowait=True).first()
    if locked_actor is None:
        raise InvitationContextChanged("Approval session unavailable")
    try:
        check_profile_bearer(db, locked_actor, bearer)
    except ProfileBearerInvalid:
        raise InvitationContextChanged("Approval session unavailable") from None
    if (not locked_actor.is_superuser and normalize_role_value(locked_actor.role) not in {"admin", "superadmin", "registrar"}):
        raise InvitationContextChanged("Approval role changed")
    locked_override = db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id == override.id).populate_existing().with_for_update(nowait=True).first()
    if (locked_override is None or locked_override.status != "approved" or locked_override.approved_by != actor.id
        or locked_override.visit_id != visit.id or locked_override.target_scope != "visit_service"
        or locked_override.target_visit_service_id is None or visit.patient_id != patient.id
        or patient.is_deleted or patient.notification_owner_generation <= 0
        or visit.status != "pending_confirmation" or visit.confirmation_context_epoch <= 0):
        raise InvitationContextChanged("Approval context changed")
    line = db.query(VisitService).filter(VisitService.id == locked_override.target_visit_service_id).populate_existing().with_for_update(nowait=True).first()
    if (line is None or line.visit_id != visit.id or line.service_id != locked_override.service_id
        or not isinstance(line.qty, int) or line.qty <= 0 or line.price is None
        or not isinstance(line.price_line_generation, int) or line.price_line_generation <= 0):
        raise InvitationContextChanged("Approved line changed")
    try:
        parse_money(line.price)
    except MoneyInputError:
        raise InvitationContextChanged("Approved line changed") from None
    return line


def stage_price_approval_invitation(db: Session, *, override: DoctorPriceOverride,
                                    actor: User, bearer: ProfileBearerContext,
                                    patient: Patient, visit: Visit) -> int | None:
    """Stage only the invitation authorized by this exact approved line.

    Caller owns User→Patient→Visit/finance locks and must flush/refresh the
    Visit after the price trigger, before issuing a token with the old expiry.
    No commit or transport occurs here.
    """
    pin_invitation_runtime(db)
    line = _check_approved_line(db, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)
    if not _valid_visit(visit, patient):
        raise InvitationContextChanged("Confirmation unavailable")
    if _has_unresolved_invitation(db, visit.id):
        # The approval owner must retain a durable recovery task instead of
        # creating another delivery while the prior outcome is uncertain.
        return None
    channel = visit.confirmation_channel or "auto"
    link = None
    if channel in {"auto", "telegram"}:
        link = _lock_verified_telegram_link(db, patient, nowait=True)
    if channel == "auto":
        channel = "telegram" if link else ("pwa" if patient.phone and patient.phone.startswith("+998") else "phone")
    if channel == "telegram" and link is None:
        return None
    if channel == "pwa":
        if not patient.phone:
            return None
        if patient.user_id is not None:
            subject = db.query(User).filter(User.id == patient.user_id).populate_existing().with_for_update(nowait=True).first()
            preferences = db.query(UserPreferences).filter(UserPreferences.user_id == patient.user_id).with_for_update(nowait=True).first()
            choices = db.query(UserNotificationSettings).filter(UserNotificationSettings.user_id == patient.user_id).with_for_update(nowait=True).first()
            if (subject is None or not subject.is_active or (preferences is not None and preferences.sms_notifications is False)
                or (choices is not None and choices.sms_appointment_confirmation is False)):
                return None
    if channel not in {"telegram", "pwa", "phone"}:
        return None
    row = VisitInvitationDelivery(visit_id=visit.id, visit_id_snapshot=visit.id,
        patient_id=patient.id, patient_id_snapshot=patient.id, owner_generation=patient.notification_owner_generation,
        context_epoch=visit.confirmation_context_epoch, token_digest=_digest(visit.confirmation_token), channel=channel,
        telegram_link_id=link.id if link else None, telegram_link_epoch=link.patient_link_epoch if link else None, state="pending")
    db.add(row)
    db.flush()
    auth = VisitInvitationPriceApprovalAuth(delivery_id=row.id, actor_user_id=actor.id,
        actor_user_id_snapshot=actor.id, actor_auth_epoch=bearer.auth_epoch,
        override_id=override.id, override_id_snapshot=override.id, line_id=line.id, line_id_snapshot=line.id,
        line_generation=line.price_line_generation, unit_price=line.price, quantity=line.qty,
        expires_at=bearer.expires_at, cipher_version=1, jti_ciphertext="")
    plain = json.dumps(_price_approval_payload(auth, jti=bearer.jti), sort_keys=True, separators=(",", ":")).encode("utf-8")
    auth.jti_ciphertext = _jti_fernet().encrypt(plain).decode("ascii")
    db.add(auth)
    db.flush()
    return row.id


def stage_price_approval_recovery(db: Session, *, override: DoctorPriceOverride, actor: User,
                                  bearer: ProfileBearerContext, patient: Patient, visit: Visit) -> int:
    """Persist an admin recovery task; fan-out is deferred until after commit."""
    pin_invitation_runtime(db)
    _check_approved_line(db, override=override, actor=actor, bearer=bearer, patient=patient, visit=visit)
    if _valid_visit(visit, patient):
        raise InvitationContextChanged("Current confirmation is still valid")
    previous = db.query(VisitInvitationApprovalRecovery).filter(
        VisitInvitationApprovalRecovery.override_id_snapshot == override.id
    ).with_for_update(nowait=True).first()
    if previous is not None:
        if (previous.visit_id == visit.id and previous.patient_id == patient.id
            and previous.owner_generation == patient.notification_owner_generation
            and previous.context_epoch == visit.confirmation_context_epoch
            and previous.actor_user_id_snapshot == actor.id and _recovery_matches_token(previous, visit)):
            return previous.id
        raise InvitationContextChanged("Recovery context changed")
    row = VisitInvitationApprovalRecovery(visit_id=visit.id, visit_id_snapshot=visit.id,
        patient_id=patient.id, patient_id_snapshot=patient.id, override_id=override.id,
        override_id_snapshot=override.id, actor_user_id_snapshot=actor.id,
        owner_generation=patient.notification_owner_generation,
        context_epoch=visit.confirmation_context_epoch,
        previous_token_digest=_digest(visit.confirmation_token) if visit.confirmation_token else None, state="pending")
    db.add(row)
    db.flush()
    return row.id


def _claim_visit_invitation(db: Session, delivery_id: int) -> ClaimedInvitation | None:
    """Claim once, committing the durable UNKNOWN state before network I/O.

    This function owns its transaction: pass a fresh session containing no
    unrelated work. A missing or already claimed attempt is never dispatched.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Invitation claim requires a clean dedicated session")
    pin_invitation_runtime(db)
    hint = db.query(VisitInvitationDelivery.patient_id, VisitInvitationDelivery.visit_id).filter(
        VisitInvitationDelivery.id == delivery_id
    ).first()
    if hint is None or hint.patient_id is None or hint.visit_id is None:
        db.rollback()
        return None
    issuer = _load_issuer(db, delivery_id)
    if issuer is None:
        _cancel_pending(db, delivery_id)
        return None
    if not _lock_and_check_issuer(db, issuer):
        _cancel_pending(db, delivery_id)
        return None
    patient = _lock_invitation_patient(db, hint.patient_id)
    visit = db.query(Visit).filter(Visit.id == hint.visit_id).populate_existing().with_for_update().first()
    row = db.query(VisitInvitationDelivery).filter(VisitInvitationDelivery.id == delivery_id).populate_existing().with_for_update().first()
    if row is None or row.state != "pending":
        db.rollback()
        return None
    # Registrar inbox delivery is transactional and must not enter the
    # external-provider UNKNOWN protocol. Its adapter is a separate slice.
    if row.channel == "phone":
        db.rollback()
        return None
    if (patient is None or visit is None or row.patient_id != hint.patient_id or row.visit_id != hint.visit_id
        or row.patient_id_snapshot != patient.id or row.visit_id_snapshot != visit.id
        or not _valid_visit(visit, patient) or row.owner_generation != patient.notification_owner_generation
        or row.context_epoch != visit.confirmation_context_epoch
        or not hmac.compare_digest(row.token_digest, _digest(visit.confirmation_token))
        or not _lock_and_check_issuer(db, issuer, visit)
        or (row.channel == "telegram" and _lock_verified_telegram_link(
            db, patient, expected_link=(row.telegram_link_id, row.telegram_link_epoch),
        ) is None)):
        row.state = "cancelled"
        db.commit()
        return None
    dispatch_nonce = secrets.token_hex(32)
    claimed = ClaimedInvitation(
        delivery_id=row.id, patient_id=patient.id, visit_id=visit.id,
        owner_generation=row.owner_generation, context_epoch=row.context_epoch,
        channel=row.channel, telegram_link_id=row.telegram_link_id,
        telegram_link_epoch=row.telegram_link_epoch, token=visit.confirmation_token,
        dispatch_nonce=dispatch_nonce,
    )
    row.state = "unknown"
    row.dispatch_nonce_digest = _digest(dispatch_nonce)
    row.updated_at = datetime.now(UTC)
    db.commit()
    return claimed


async def _send_claimed_visit_invitation(db: Session, claimed: ClaimedInvitation, sender) -> bool:
    """Consume a claim once, then send neutral SMS/Telegram under subject locks.

    The UNKNOWN row is durable already. A crash, timeout, rejection, or failed
    DB commit remains UNKNOWN, even if the provider might have accepted it.
    ``phone`` requires a separate atomic registrar-inbox transaction and is not
    dispatched through this external-provider method.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Invitation dispatch requires a clean dedicated session")
    pin_invitation_runtime(db)
    if claimed.channel not in {"telegram", "pwa"}:
        return False
    nonce_digest = _digest(claimed.dispatch_nonce)
    count = db.query(VisitInvitationDelivery).filter(
        VisitInvitationDelivery.id == claimed.delivery_id,
        VisitInvitationDelivery.state == "unknown",
        VisitInvitationDelivery.dispatch_nonce_digest == nonce_digest,
    ).update({VisitInvitationDelivery.dispatch_nonce_digest: None}, synchronize_session=False)
    if count != 1:
        db.rollback()
        return False
    db.commit()  # The in-memory dispatch capability can never be used twice.
    pin_invitation_runtime(db)

    # Probe only selects a lock target; every fact is checked again under lock.
    user_id = db.query(Patient.user_id).filter(Patient.id == claimed.patient_id).scalar()
    issuer = _load_issuer(db, claimed.delivery_id)
    if issuer is None or issuer.actor_user_id is None:
        db.rollback()
        return False
    user_ids = sorted({value for value in (user_id, issuer.actor_user_id) if value is not None})
    users = db.query(User).filter(User.id.in_(user_ids)).order_by(User.id).populate_existing().with_for_update(nowait=True).all()
    by_id = {item.id: item for item in users}
    user = by_id.get(user_id) if user_id is not None else None
    if not _lock_and_check_issuer(db, issuer):
        db.rollback()
        return False
    patient = _lock_invitation_patient(db, claimed.patient_id)
    visit = db.query(Visit).filter(Visit.id == claimed.visit_id).populate_existing().with_for_update().first()
    row = db.query(VisitInvitationDelivery).filter(
        VisitInvitationDelivery.id == claimed.delivery_id
    ).populate_existing().with_for_update().first()
    if (patient is None or visit is None or row is None or row.state != "unknown"
        or row.visit_id != visit.id or row.patient_id != patient.id
        or patient.user_id != user_id or (user_id is not None and (user is None or not user.is_active))
        or patient.notification_owner_generation != claimed.owner_generation
        or row.owner_generation != claimed.owner_generation or row.context_epoch != claimed.context_epoch
        or visit.confirmation_context_epoch != claimed.context_epoch or not _valid_visit(visit, patient)
        or not hmac.compare_digest(visit.confirmation_token, claimed.token)
        or not hmac.compare_digest(row.token_digest, _digest(claimed.token))
        or row.channel != claimed.channel or not _lock_and_check_issuer(db, issuer, visit)):
        db.rollback()
        return False

    data = {"visit_id": visit.id, "confirmation_token": claimed.token,
            "confirmation_context_epoch": claimed.context_epoch}
    if claimed.channel == "telegram":
        if ((row.telegram_link_id, row.telegram_link_epoch) != (claimed.telegram_link_id, claimed.telegram_link_epoch)
            or _lock_verified_telegram_link(
                db, patient, expected_link=(claimed.telegram_link_id, claimed.telegram_link_epoch),
            ) is None):
            db.rollback()
            return False
        operation = sender._send_telegram_invitation(
            patient, data, db=db,
            expected_link=(claimed.telegram_link_id, claimed.telegram_link_epoch),
        )
    else:
        # User row protects an absent FK-backed preference from concurrent
        # insertion; existing rows are also locked against updates/deletes.
        if user_id is not None:
            preferences = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).with_for_update().first()
            settings = db.query(UserNotificationSettings).filter(UserNotificationSettings.user_id == user_id).with_for_update().first()
            if ((preferences is not None and preferences.sms_notifications is False)
                or (settings is not None and settings.sms_appointment_confirmation is False)):
                db.rollback()
                return False
        operation = sender._send_pwa_invitation(patient, data, db=db, sms_opted_in=True)
    try:
        result = await asyncio.wait_for(operation, timeout=15)
    except Exception:
        db.rollback()
        return False
    if not isinstance(result, dict) or result.get("success") is not True:
        db.rollback()
        return False
    row.state = "sent"
    row.updated_at = datetime.now(UTC)
    db.commit()
    return True


async def _deliver_registrar_invitation(db: Session, delivery_id: int, sender) -> bool:
    """Create a neutral registrar inbox task and mark its intent atomically.

    No provider call or WebSocket notification occurs before commit. The
    opaque task handle only permits access through the authorized read API.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Registrar delivery requires a clean dedicated session")
    pin_invitation_runtime(db)
    hint = db.query(VisitInvitationDelivery.patient_id, VisitInvitationDelivery.visit_id).filter(
        VisitInvitationDelivery.id == delivery_id
    ).first()
    if hint is None or hint.patient_id is None or hint.visit_id is None:
        db.rollback()
        return False
    issuer = _load_issuer(db, delivery_id)
    if issuer is None or issuer.actor_user_id is None:
        _cancel_pending(db, delivery_id)
        return False
    platform = sender._platform_service(db)
    recipient_ids = sorted({user.id for user in platform.resolve_users_for_role("registrar")})
    if not recipient_ids:
        if not _lock_and_check_issuer(db, issuer):
            _cancel_pending(db, delivery_id)
        else:
            db.rollback()
        return False
    all_user_ids = sorted(set(recipient_ids) | {issuer.actor_user_id})
    users = db.query(User).filter(User.id.in_(all_user_ids)).order_by(User.id).populate_existing().with_for_update(nowait=True).all()
    users = [user for user in users if user.id in recipient_ids and user.is_active and (user.role or "").strip().lower() == "registrar"]
    if not _lock_and_check_issuer(db, issuer):
        _cancel_pending(db, delivery_id)
        return False
    if not users:
        db.rollback()
        return False
    patient = _lock_invitation_patient(db, hint.patient_id)
    visit = db.query(Visit).filter(Visit.id == hint.visit_id).populate_existing().with_for_update().first()
    row = db.query(VisitInvitationDelivery).filter(VisitInvitationDelivery.id == delivery_id).populate_existing().with_for_update().first()
    if (patient is None or visit is None or row is None or row.state != "pending" or row.channel != "phone"
        or row.patient_id != patient.id or row.visit_id != visit.id or not _valid_visit(visit, patient)
        or row.owner_generation != patient.notification_owner_generation
        or row.context_epoch != visit.confirmation_context_epoch
        or not hmac.compare_digest(row.token_digest, _digest(visit.confirmation_token))
        or not _lock_and_check_issuer(db, issuer, visit)):
        _cancel_pending(db, delivery_id)
        return False

    opaque = str(uuid4())
    title, message = "Задача регистратуре", "Вам доступна новая задача."
    snapshot = {"title": title, "message": message, "metadata": {}}
    event = platform._create_or_get_event(
        event_type="appointment_confirmation_task", source_module="visit_confirmation_secure",
        scope_key=f"invitation:{row.id}", title=title, message=message,
        severity="warning", priority="high", correlation_id=opaque,
        actor_id=None, actor_role=None, entity_type="visit_invitation_delivery", entity_id=row.id,
        payload_snapshot=snapshot, deep_link=f"/registrar?invitation={opaque}",
        expires_at=visit.confirmation_expires_at,
    )
    deliveries = [platform._create_or_get_delivery(
        event=event, recipient_type="user", recipient_id=user.id, role="registrar",
        department_key=None, channel=platform.INBOX_CHANNEL, payload_snapshot=snapshot,
    ) for user in users]
    row.state = "sent"
    row.updated_at = datetime.now(UTC)
    db.commit()
    # The canonical payload contains only the neutral text and opaque handle.
    for user, delivery in zip(users, deliveries, strict=True):
        try:
            await platform._broadcast_delivery(user.id, delivery)
        except Exception:
            # Inbox is durable; broadcast failure must not repeat creation.
            pass
    return True


async def _deliver_price_approval_recovery(db: Session, recovery_id: int, sender) -> bool:
    """Fan out a neutral admin task atomically; keep pending if no admin exists."""
    if db.new or db.dirty or db.deleted:
        raise ValueError("Recovery delivery requires a clean dedicated session")
    pin_invitation_runtime(db)
    hint = db.query(VisitInvitationApprovalRecovery.patient_id, VisitInvitationApprovalRecovery.visit_id).filter(
        VisitInvitationApprovalRecovery.id == recovery_id
    ).first()
    if hint is None or hint.patient_id is None or hint.visit_id is None:
        db.rollback()
        return False
    ids = [item.id for item in db.query(User.id).filter(User.is_active.is_(True),
           (sa_func.lower(User.role) == "admin") | User.is_superuser.is_(True)).order_by(User.id).all()]
    admins = (db.query(User).filter(User.id.in_(ids)).order_by(User.id).populate_existing().with_for_update(nowait=True).all()) if ids else []
    admins = [item for item in admins if item.is_active and (item.is_superuser or normalize_role_value(item.role) == "admin")]
    patient = _lock_invitation_patient(db, hint.patient_id)
    visit = db.query(Visit).filter(Visit.id == hint.visit_id).populate_existing().with_for_update().first()
    recovery = db.query(VisitInvitationApprovalRecovery).filter(VisitInvitationApprovalRecovery.id == recovery_id).populate_existing().with_for_update(nowait=True).first()
    if recovery is None or recovery.state != "pending":
        db.rollback()
        return False
    override = (db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id == recovery.override_id)
                .populate_existing().with_for_update(nowait=True).first()) if recovery.override_id is not None else None
    if (patient is None or visit is None or override is None or patient.is_deleted
        or recovery.patient_id != patient.id or recovery.visit_id != visit.id
        or visit.patient_id != patient.id or visit.status != "pending_confirmation"
        or patient.notification_owner_generation != recovery.owner_generation
        or visit.confirmation_context_epoch != recovery.context_epoch
        or override.status != "approved" or override.approved_by != recovery.actor_user_id_snapshot
        or override.visit_id != visit.id or not _recovery_matches_token(recovery, visit)
        or _valid_visit(visit, patient)):
        recovery.state = "resolved"
        db.commit()
        return False
    if not admins:
        db.rollback()
        return False
    platform = sender._platform_service(db)
    opaque = str(uuid4())
    title, message = "Задача администратору", "Требуется проверить подтверждение визита."
    snapshot = {"title": title, "message": message, "metadata": {}}
    event = platform._create_or_get_event(
        event_type="visit_confirmation_reissue_required", source_module="visit_confirmation_recovery",
        scope_key=f"recovery:{recovery.id}", title=title, message=message, severity="warning", priority="high",
        correlation_id=opaque, actor_id=None, actor_role=None,
        entity_type="visit_invitation_approval_recovery", entity_id=recovery.id,
        payload_snapshot=snapshot, deep_link=f"/admin?invitation_recovery={opaque}", expires_at=None,
    )
    deliveries = [platform._create_or_get_delivery(event=event, recipient_type="user", recipient_id=user.id,
        role="admin", department_key=None, channel=platform.INBOX_CHANNEL, payload_snapshot=snapshot) for user in admins]
    recovery.state = "dispatched"
    db.commit()
    for user, delivery in zip(admins, deliveries, strict=True):
        try:
            await platform._broadcast_delivery(user.id, delivery)
        except Exception:
            pass
    return True


def _lock_conflict(exc: DBAPIError) -> bool:
    original = exc.orig
    return (getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)) in {"55P03", "40P01"}


def claim_visit_invitation(db: Session, delivery_id: int) -> ClaimedInvitation | None:
    try:
        return _claim_visit_invitation(db, delivery_id)
    except DBAPIError as exc:
        db.rollback()
        if _lock_conflict(exc):
            return None
        raise


async def send_claimed_visit_invitation(db: Session, claimed: ClaimedInvitation, sender) -> bool:
    try:
        return await _send_claimed_visit_invitation(db, claimed, sender)
    except DBAPIError as exc:
        db.rollback()
        if _lock_conflict(exc):
            return False
        raise


async def deliver_registrar_invitation(db: Session, delivery_id: int, sender) -> bool:
    try:
        return await _deliver_registrar_invitation(db, delivery_id, sender)
    except DBAPIError as exc:
        db.rollback()
        if _lock_conflict(exc):
            return False
        raise


async def deliver_price_approval_recovery(db: Session, recovery_id: int, sender) -> bool:
    try:
        return await _deliver_price_approval_recovery(db, recovery_id, sender)
    except DBAPIError as exc:
        db.rollback()
        if _lock_conflict(exc):
            return False
        raise
