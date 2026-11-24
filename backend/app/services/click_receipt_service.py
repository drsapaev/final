"""Store bounded Click observations; never issue ACK or mutate payments.

The caller must use a fresh Session and cannot send an ACK merely because a
receipt was returned. The independent prepare/settlement reducer is required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.capability_namespace import capability_schema_name
from app.models.click_callback_receipt import (
    ClickCallbackReceipt,
    ClickReceiptKeyVersion,
)
from app.services.click_webhook_protocol import (
    ClickProtocolError,
    authenticate_click_receipt,
    parse_click_fields,
)

_VERSION = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}\Z")
_DOMAIN = b"click-receipt-aes-siv-v1"
_COMMITMENT = b"click-receipt-key-commitment-v1"


class ClickReceiptError(ValueError):
    """Ingress failed; caller must not ACK or log callback payload."""


@dataclass(frozen=True)
class StoredClickReceipt:
    id: int
    created: bool
    confidence: str
    # Deliberately no provider ACK, payment state, or authorization value.


def receipt_key_commitment(key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) != 64:
        raise ClickReceiptError("receipt key unavailable")
    return hmac.new(key, _COMMITMENT, hashlib.sha256).hexdigest()


def configured_receipt_keys(secret, active_version: str | None) -> dict[str, bytes]:
    """Decode explicit versioned AESSIV keys without exposing config values."""
    def pairs(values):
        result = {}
        for name, value in values:
            if name in result:
                raise ValueError("duplicate version")
            result[name] = value
        return result

    try:
        if secret is None or not isinstance(active_version, str) or not _VERSION.fullmatch(active_version):
            raise ValueError("missing keyring")
        raw = secret.get_secret_value()
        if not isinstance(raw, str) or len(raw) > 16_384:
            raise ValueError("invalid keyring")
        encoded = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(encoded, dict) or not 1 <= len(encoded) <= 32 or active_version not in encoded:
            raise ValueError("invalid keyring")
        keys = {}
        for version, value in encoded.items():
            if not isinstance(version, str) or not _VERSION.fullmatch(version) or not isinstance(value, str):
                raise ValueError("invalid keyring")
            key = base64.b64decode(value, validate=True)
            receipt_key_commitment(key)
            keys[version] = key
        return keys
    except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise ClickReceiptError("receipt key unavailable") from None


def configured_webhook_credentials(retained, current_service: str | None,
                                   current_secret: str | None) -> tuple[tuple[str, str], ...]:
    """Return current/retained signature keys without exposing secret values.

    A disabled checkout does not disable verification of late callbacks.
    Operators must retain retired secrets through the provider retry and
    reconciliation window; an unknown signature never earns an ACK.
    """
    try:
        contexts: list[tuple[str, str]] = []
        if current_service is not None or current_secret is not None:
            contexts.append((current_service, current_secret))
        if retained is not None:
            raw = retained.get_secret_value()
            if not isinstance(raw, str) or len(raw) > 32_768:
                raise ValueError("invalid credentials")
            def unique(values):
                result = {}
                for name, value in values:
                    if name in result:
                        raise ValueError("duplicate field")
                    result[name] = value
                return result
            entries = json.loads(raw, object_pairs_hook=unique)
            if not isinstance(entries, list) or len(entries) > 16:
                raise ValueError("invalid credentials")
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {"service_id", "secret"}:
                    raise ValueError("invalid credentials")
                contexts.append((entry["service_id"], entry["secret"]))
        if not contexts or len(contexts) > 17:
            raise ValueError("missing credentials")
        unique_contexts = []
        for service, secret in contexts:
            if (not isinstance(service, str) or not service or len(service) > 128
                    or not isinstance(secret, str) or not secret or len(secret) > 2048
                    or any(ord(char) < 32 or ord(char) == 127 for char in service + secret)):
                raise ValueError("invalid credentials")
            service.encode("utf-8", errors="strict")
            secret.encode("utf-8", errors="strict")
            if not any(service == old_service and hmac.compare_digest(secret.encode(), old_secret.encode())
                       for old_service, old_secret in unique_contexts):
                unique_contexts.append((service, secret))
        return tuple(unique_contexts)
    except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise ClickReceiptError("webhook credentials unavailable") from None


def select_webhook_credential(body: bytes, content_type: str,
                              contexts: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    """Choose one signature-verifying credential, never an arbitrary payload."""
    fields = parse_click_fields(body, content_type)
    matches = []
    for service, secret in contexts:
        try:
            authenticate_click_receipt(fields, service_id=service, secret_key=secret)
        except ClickProtocolError:
            continue
        matches.append((service, secret))
    # Multiple distinct secret keys authenticating one concatenated payload
    # cannot safely select an issuance context, even if astronomically rare.
    if len(matches) != 1:
        raise ClickProtocolError("unverified callback")
    return matches[0]


def _key(keyring: dict[str, bytes], version: str) -> bytes:
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ClickReceiptError("receipt key unavailable")
    if not isinstance(keyring, dict):
        raise ClickReceiptError("receipt key unavailable")
    value = keyring.get(version)
    receipt_key_commitment(value)
    return value


def _aad(event_key: str, digest: str, phase: str, confidence: str, media_type: str, version: str) -> list[bytes]:
    return [_DOMAIN, event_key.encode(), digest.encode(), phase.encode(), confidence.encode(), media_type.encode(), version.encode()]


def reconciliation_receipt_capability(db, schema: str, backend_role: str | None = None) -> int | None:
    """Recognize only the separately provisioned, non-login 0123 reader.

    Called while holding ACCESS SHARE on the receipt tables. An absent policy
    means 0123 has not been provisioned; a malformed one is always an error.
    """
    row = db.execute(text("""
      SELECT p.polcmd, p.polpermissive, p.polroles,
        pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
        pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked,
        r.oid AS role_id, r.rolcanlogin, r.rolsuper, r.rolbypassrls,
        r.rolcreaterole, r.rolcreatedb, r.rolreplication,
        pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE') AS creates,
        priv.oid IS NOT NULL AND priv.nspowner=n.nspowner AND NOT EXISTS (
          SELECT 1 FROM pg_catalog.aclexplode(COALESCE(priv.nspacl,pg_catalog.acldefault('n',priv.nspowner))) a
          WHERE (a.privilege_type='CREATE' AND a.grantee<>priv.nspowner) OR a.grantee=0
        ) AS private_trusted,
        pg_catalog.has_column_privilege(r.oid,c.oid,'phase','SELECT')
          AND NOT pg_catalog.has_table_privilege(r.oid,c.oid,'SELECT') AS phase_only,
        EXISTS (SELECT 1 FROM pg_catalog.pg_roles x WHERE x.oid<>r.oid AND
          (pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER') OR
           (NOT x.rolsuper AND pg_catalog.pg_has_role(x.oid,r.oid,'MEMBER')))) AS memberships,
        EXISTS (SELECT 1 FROM pg_catalog.pg_proc f WHERE f.pronamespace=priv.oid
          AND f.proname='reconciliation_pending_guard' AND f.pronargs=0
          AND f.proowner=r.oid AND f.prosecdef
          AND 'search_path=pg_catalog'=ANY(f.proconfig)
          AND 'row_security=on'=ANY(f.proconfig)
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(f.proacl,pg_catalog.acldefault('f',f.proowner))) a
            WHERE a.grantee NOT IN (f.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=COALESCE(:backend_role,CURRENT_USER)))
               OR (a.grantee<>f.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable)))) AS owns_guard
      FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_class c ON c.relnamespace=n.oid
      LEFT JOIN pg_catalog.pg_namespace priv ON priv.nspname=:private
      JOIN pg_catalog.pg_policy p ON p.polrelid=c.oid
      LEFT JOIN pg_catalog.pg_roles r ON r.oid=p.polroles[pg_catalog.array_lower(p.polroles,1)]
      WHERE n.nspname=:schema AND c.relname='click_callback_receipts'
        AND p.polname='reconciliation_cap_select'
    """), {"schema": schema, "private": capability_schema_name(schema), "backend_role": backend_role}).mappings().one_or_none()
    if row is None:
        return None
    role_id = row["role_id"]
    if not (role_id and row["polcmd"] == "r" and row["polpermissive"]
            and list(row["polroles"]) == [role_id] and row["qual"] == "true"
            and row["checked"] is None and row["owns_guard"] and row["private_trusted"] and row["phase_only"] and not row["creates"]
            and not row["memberships"] and not any(row[key] for key in
              ("rolcanlogin", "rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))):
        raise ClickReceiptError("receipt database role unavailable")
    return role_id


class ClickReceiptService:
    """Authenticated observations, encrypted and committed before return."""

    def __init__(self, db: Session, *, keyring: dict[str, bytes], active_version: str,
                 trusted_schema: str | None = None, trusted_owner: str | None = None,
                 trusted_owner_members: tuple[str, ...] = ()):
        self.db = db
        self.keyring = keyring
        self.active_version = active_version
        self.trusted_schema = trusted_schema
        self.trusted_owner = trusted_owner
        self.trusted_owner_members = trusted_owner_members

    def _prepare_pg_role(self) -> None:
        schema, owner = self.trusted_schema, self.trusted_owner
        if not isinstance(schema, str) or not schema or not isinstance(owner, str) or not owner:
            raise ClickReceiptError("receipt database role unavailable")
        members = self.trusted_owner_members
        try:
            if (not isinstance(members, tuple) or len(members) > 64 or len(set(members)) != len(members)
                    or any(not isinstance(x, str) or not x or len(x.encode("utf-8")) > 63
                           or "\0" in x or x.lower() in {"public", "anon", "authenticated"} for x in members)):
                raise ValueError("invalid trusted profile")
        except (UnicodeError, TypeError, ValueError):
            raise ClickReceiptError("receipt database role unavailable") from None
        # Pin every subsequent unqualified ORM relation to the trusted schema.
        quote = self.db.get_bind().dialect.identifier_preparer.quote_schema
        self.db.execute(text(f"SET LOCAL search_path TO pg_catalog, {quote(schema)}, pg_temp"))
        self.db.execute(text(f"LOCK TABLE {quote(schema)}.click_receipt_key_versions, {quote(schema)}.click_callback_receipts IN ACCESS SHARE MODE"))
        capability_id = reconciliation_receipt_capability(self.db, schema)
        safe = self.db.execute(text("""
        WITH actor AS (
          SELECT oid, rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication
          FROM pg_catalog.pg_roles WHERE rolname = CURRENT_USER
        ), owner_role AS (SELECT oid,rolcanlogin,rolsuper FROM pg_catalog.pg_roles WHERE rolname=:owner),
        ns AS (SELECT oid, nspowner, nspacl FROM pg_catalog.pg_namespace WHERE nspname=:schema),
        tables AS (
          SELECT c.oid,c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c JOIN ns ON ns.oid=c.relnamespace
          WHERE c.relname IN ('click_receipt_key_versions','click_callback_receipts') AND c.relkind='r'
        )
        SELECT COUNT(*)=2 AND COALESCE(bool_and(t.relowner=o.oid AND t.relrowsecurity AND t.relforcerowsecurity), false)
          AND ns.nspowner=o.oid AND NOT pg_catalog.has_schema_privilege(CURRENT_USER,ns.oid,'CREATE')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(ns.nspacl,pg_catalog.acldefault('n',ns.nspowner))) x
                          WHERE x.privilege_type='CREATE' AND x.grantee<>o.oid)
          AND NOT a.rolsuper AND NOT a.rolbypassrls AND NOT a.rolcreaterole AND NOT a.rolcreatedb AND NOT a.rolreplication
          AND CURRENT_USER=SESSION_USER AND pg_catalog.lower(a.rolname) NOT IN ('anon','authenticated','public')
          AND NOT pg_catalog.pg_has_role(a.oid,o.oid,'MEMBER')
          AND (o.rolsuper OR NOT o.rolcanlogin)
          AND COALESCE((SELECT pg_catalog.array_agg(member.rolname::text ORDER BY member.rolname::text)
                        FROM pg_catalog.pg_roles member WHERE member.oid<>o.oid AND NOT member.rolsuper
                          AND pg_catalog.pg_has_role(member.oid,o.oid,'MEMBER')), ARRAY[]::text[]) = CAST(:owner_members AS text[])
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles member WHERE member.oid<>o.oid AND NOT member.rolsuper
              AND pg_catalog.pg_has_role(member.oid,o.oid,'MEMBER')
              AND (member.rolbypassrls OR member.rolcreaterole OR member.rolcreatedb OR member.rolreplication))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles other WHERE NOT other.rolsuper AND other.oid<>a.oid
                          AND pg_catalog.pg_has_role(other.oid,a.oid,'MEMBER'))
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
                          AND pg_catalog.pg_has_role(a.oid,r.oid,'MEMBER'))
          AND COALESCE(bool_and(pg_catalog.has_table_privilege(a.oid,t.oid,'SELECT')
              AND NOT pg_catalog.has_table_privilege(a.oid,t.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
              AND NOT pg_catalog.has_any_column_privilege(a.oid,t.oid,'UPDATE,REFERENCES')
              AND CASE WHEN t.relname='click_callback_receipts' THEN pg_catalog.has_table_privilege(a.oid,t.oid,'INSERT')
                       ELSE NOT pg_catalog.has_table_privilege(a.oid,t.oid,'INSERT') END),false)
          AND COALESCE(bool_and(NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_class c,
              LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x
            WHERE c.oid=t.oid AND x.grantee<>t.relowner AND NOT (
              x.grantee=a.oid AND NOT x.is_grantable AND
              (x.privilege_type='SELECT' OR (t.relname='click_callback_receipts' AND x.privilege_type='INSERT')))
          ) AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_attribute col,LATERAL pg_catalog.aclexplode(col.attacl) x
            WHERE col.attrelid=t.oid AND col.attnum>0 AND NOT col.attisdropped AND x.grantee<>t.relowner
              AND NOT (t.relname='click_callback_receipts' AND col.attname='phase'
                AND x.grantee=CAST(:capability_id AS oid) AND x.privilege_type='SELECT' AND NOT x.is_grantable)
          )),false)
          AND COALESCE(bool_and(NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=t.oid AND p.polname NOT IN
              ('click_receipt_owner_select','click_receipt_owner_insert','click_receipt_backend_select','click_receipt_backend_insert')
              AND NOT (t.relname='click_callback_receipts' AND p.polname='reconciliation_cap_select'
                       AND CAST(:capability_id AS oid) IS NOT NULL)
          )),false)
          AND COALESCE(bool_and(EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=t.oid AND p.polname='click_receipt_backend_select'
              AND p.polcmd='r' AND p.polpermissive AND p.polroles=ARRAY[a.oid]::oid[]
              AND pg_catalog.pg_get_expr(p.polqual,t.oid)='true'
          )),false)
          AND COALESCE(bool_and(CASE WHEN t.relname='click_callback_receipts' THEN EXISTS (
            SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=t.oid AND p.polname='click_receipt_backend_insert'
              AND p.polcmd='a' AND p.polpermissive AND p.polroles=ARRAY[a.oid]::oid[]
              AND pg_catalog.pg_get_expr(p.polwithcheck,t.oid)='true') ELSE true END),false)
          AND (SELECT pg_catalog.has_sequence_privilege(a.oid,s.oid,'USAGE')
                   AND NOT pg_catalog.has_sequence_privilege(a.oid,s.oid,'UPDATE')
                   AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(s.relacl,pg_catalog.acldefault('S',s.relowner))) x
                        WHERE x.grantee<>s.relowner AND NOT (x.grantee=a.oid AND x.privilege_type='USAGE' AND NOT x.is_grantable))
               FROM pg_catalog.pg_class s WHERE s.relnamespace=ns.oid
                 AND s.relname='click_callback_receipts_id_seq' AND s.relkind='S')
        FROM tables t CROSS JOIN actor a CROSS JOIN owner_role o CROSS JOIN ns
        GROUP BY a.oid,a.rolname,a.rolsuper,a.rolbypassrls,a.rolcreaterole,a.rolcreatedb,a.rolreplication,o.oid,o.rolcanlogin,o.rolsuper,ns.oid,ns.nspowner,ns.nspacl
        """), {"schema": schema, "owner": owner, "capability_id": capability_id, "owner_members": sorted(members)}).scalar_one_or_none()
        if safe is not True:
            raise ClickReceiptError("receipt database role unavailable")

    def _check_registered_key(self, version: str) -> bytes:
        key = _key(self.keyring, version)
        row = self.db.query(ClickReceiptKeyVersion).filter_by(version=version).first()
        if row is None or not hmac.compare_digest(row.commitment, receipt_key_commitment(key)):
            raise ClickReceiptError("receipt key unavailable")
        return key

    def _decrypt(self, row: ClickCallbackReceipt) -> bytes:
        with self.db.no_autoflush:
            key = self._check_registered_key(row.key_version)
            try:
                body = AESSIV(key).decrypt(row.ciphertext, _aad(row.event_key, row.body_digest, row.phase,
                                                               row.confidence, row.media_type, row.key_version))
            except (InvalidTag, ValueError):
                raise ClickReceiptError("receipt integrity unavailable") from None
            digest = hashlib.sha256(row.media_type.encode() + b"\0" + body).hexdigest()
            if len(body) != row.body_size or not hmac.compare_digest(digest, row.body_digest):
                raise ClickReceiptError("receipt integrity unavailable")
            return body

    def store(self, *, body: bytes, content_type: str, service_id: str, secret_key: str) -> StoredClickReceipt:
        if self.db.in_transaction() or self.db.new or self.db.dirty or self.db.deleted:
            raise ClickReceiptError("fresh receipt transaction required")
        fields = parse_click_fields(body, content_type)
        observation, confidence = authenticate_click_receipt(fields, service_id=service_id, secret_key=secret_key)
        media = content_type.split(";", 1)[0].strip().lower()
        phase = "complete" if observation.action else "prepare"
        # Length-prefixed domain components prevent concatenation ambiguity in
        # our own idempotency key (Click's external signature has none).
        material = b"".join(len(part).to_bytes(4, "big") + part for part in
                            (b"click", service_id.encode(), observation.transaction_id.encode(), phase.encode()))
        event_key = hashlib.sha256(material).hexdigest()
        digest = hashlib.sha256(media.encode() + b"\0" + body).hexdigest()
        try:
            with self.db.begin():
                dialect = self.db.get_bind().dialect.name
                if dialect == "postgresql":
                    isolation = self.db.execute(text("SHOW transaction_isolation")).scalar_one()
                    if isolation != "read committed":
                        raise ClickReceiptError("receipt transaction isolation unavailable")
                    self._prepare_pg_role()
                    lock_id = int.from_bytes(bytes.fromhex(event_key)[:8], "big", signed=True)
                    self.db.execute(text("SELECT pg_catalog.pg_advisory_xact_lock(:key)"), {"key": lock_id})
                elif dialect == "sqlite":
                    self.db.execute(text("UPDATE click_callback_receipts SET id=id WHERE 0"))
                else:
                    raise ClickReceiptError("unsupported receipt database")
                rows = (self.db.query(ClickCallbackReceipt)
                        .filter(ClickCallbackReceipt.event_key == event_key)
                        .order_by(ClickCallbackReceipt.variant_slot).all())
                for row in rows:
                    if hmac.compare_digest(row.body_digest, digest):
                        if not hmac.compare_digest(self._decrypt(row), body):
                            raise ClickReceiptError("receipt integrity unavailable")
                        result = StoredClickReceipt(row.id, False, row.confidence)
                        break
                else:
                    occupied = {row.variant_slot for row in rows}
                    available = next((slot for slot in range(32) if slot not in occupied), None)
                    if available is None:
                        raise ClickReceiptError("receipt variants require operator reconciliation")
                    key = self._check_registered_key(self.active_version)
                    ciphertext = AESSIV(key).encrypt(body, _aad(event_key, digest, phase, confidence, media, self.active_version))
                    row = ClickCallbackReceipt(event_key=event_key, body_digest=digest, variant_slot=available,
                        phase=phase, confidence=confidence, media_type=media, body_size=len(body),
                        key_version=self.active_version, ciphertext=ciphertext)
                    self.db.add(row)
                    self.db.flush()
                    result = StoredClickReceipt(row.id, True, confidence)
            # Context manager has committed successfully before any return.
            return result
        except SQLAlchemyError:
            raise ClickReceiptError("receipt storage unavailable") from None
