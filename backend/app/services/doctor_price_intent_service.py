"""Durable doctor-price request identity, without authorization or delivery.

The caller must own the entire transaction, reauthorize the actor and target,
and only bind a new key alias after revalidating the live result. On a conflict
the caller must roll back the root transaction before a fresh attempt.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import hashlib
import hmac
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


class PriceIntentUnavailable(RuntimeError):
    """Required state is unavailable; callers must roll back and fail closed."""


class PriceIntentConflict(RuntimeError):
    """A retry cannot safely be associated with one result."""


class PriceIntentRetryable(PriceIntentConflict):
    """A lock conflict requires rollback and a fresh authorized retry."""


class PriceIntentPending(PriceIntentRetryable):
    """A prior same-actor operation may still be in flight."""
    code = "pending_outcome"


class PriceIntentAmbiguous(PriceIntentConflict):
    """An unkeyed or unspecified request may duplicate a prior operation."""
    code = "ambiguous_retry"


class PriceIntentInvalid(ValueError):
    """An input cannot be represented by the canonical intent contract."""


_UNAVAILABLE = "Doctor price idempotency is unavailable"
_CONFLICT = "Doctor price request conflicts with an existing request"
_INVALID = "Invalid doctor price request identity"
_OPERATIONS = frozenset({"schedule_next", "add_service"})
_MAX_INT = 2147483647
_VERSION = re.compile(r"[1-9][0-9]*\Z")
_MAX_DOCUMENT_BYTES = 65536
_MAX_CANDIDATES = 10000


def _raise_database_error(exc: DBAPIError, *, conflict: bool = False) -> None:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    sqlite_code = getattr(original, "sqlite_errorcode", None)
    if sqlstate == "55P03" or (isinstance(sqlite_code, int) and sqlite_code & 255 in (5, 6)):
        raise PriceIntentRetryable(_CONFLICT) from None
    if conflict and (sqlstate in {"23503", "23505"} or sqlite_code in {787, 1555, 2067}):
        raise PriceIntentConflict(_CONFLICT) from None
    if sqlstate == "42501" or (isinstance(sqlstate, str) and sqlstate.startswith("08")):
        raise PriceIntentUnavailable(_UNAVAILABLE) from None
    raise exc


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


@dataclass(frozen=True, repr=False)
class PriceIntentKeyring:
    active_version: int
    _keys: dict[int, bytes] = field(repr=False)

    @classmethod
    def from_settings(cls, settings: Any) -> PriceIntentKeyring:
        try:
            raw = settings.DOCTOR_PRICE_HMAC_KEYS
            if hasattr(raw, "get_secret_value"):
                raw = raw.get_secret_value()
            if not isinstance(raw, str) or len(raw) > 65536:
                raise ValueError("missing")
            data = json.loads(raw, object_pairs_hook=_unique_pairs)
            if not isinstance(data, dict) or not 1 <= len(data) <= 256:
                raise ValueError("invalid")
            keys: dict[int, bytes] = {}
            for name, encoded in data.items():
                if not isinstance(name, str) or not _VERSION.fullmatch(name) or len(name) > 10:
                    raise ValueError("version")
                version = int(name)
                if version > _MAX_INT or not isinstance(encoded, str):
                    raise ValueError("invalid")
                # Require canonical URL-safe base64 encoding of exactly 256 bits.
                decoded = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
                if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).decode("ascii") != encoded:
                    raise ValueError("invalid")
                keys[version] = decoded
            active = settings.DOCTOR_PRICE_HMAC_ACTIVE_VERSION
            if type(active) is not int or active not in keys:
                raise ValueError("active")
            return cls(active, keys)
        except (AttributeError, TypeError, ValueError, OverflowError, UnicodeError, binascii.Error, RecursionError):
            raise PriceIntentUnavailable(_UNAVAILABLE) from None

    def _digest(self, version: int, domain: bytes, content: bytes) -> str:
        key = self._keys.get(version)
        if key is None:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        message = b"doctor-price:v1\x00" + domain + b"\x00" + str(version).encode("ascii") + b"\x00" + content
        return hmac.new(key, message, hashlib.sha256).hexdigest()

    def commitment(self, version: int) -> str:
        return self._digest(version, b"key-check", b"")


def _check_value(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise PriceIntentInvalid(_INVALID)
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise PriceIntentInvalid(_INVALID) from None
        return
    if type(value) is list:
        for item in value:
            _check_value(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise PriceIntentInvalid(_INVALID)
            _check_value(key, depth + 1)
            _check_value(item, depth + 1)
        return
    raise PriceIntentInvalid(_INVALID)


def _canonical(value: Any) -> bytes:
    _check_value(value)
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise PriceIntentInvalid(_INVALID) from None
    if len(result) > _MAX_DOCUMENT_BYTES:
        raise PriceIntentInvalid(_INVALID)
    return result


def _key_hash(key: str) -> str:
    if not isinstance(key, str) or not 1 <= len(key) <= 128 or any(ord(c) < 32 or ord(c) == 127 for c in key):
        raise PriceIntentInvalid(_INVALID)
    try:
        value = key.encode("utf-8")
    except UnicodeError:
        raise PriceIntentInvalid(_INVALID) from None
    return hashlib.sha256(b"doctor-price-idempotency-key:v1\x00" + value).hexdigest()


@dataclass(frozen=True)
class LookupResult:
    intent_id: int | None
    needs_alias: bool = False


class DoctorPriceIntentService:
    """Transaction-local helper. It never commits or grants access."""

    def __init__(self, db: Session, keyring: PriceIntentKeyring, schema: str | None = None,
                 schema_owner: str | None = None, runtime_role: str | None = None):
        self.db = db
        self.keyring = keyring
        self.schema = schema
        self.schema_owner = schema_owner
        self.runtime_role = runtime_role
        self._scope: tuple[int, str] | None = None
        self._transaction = None
        self._sqlite_writer = False
        self._registry_transaction = None
        self._schema_transaction = None

    def reserve_sqlite_writer(self) -> None:
        """Call before *any* transaction read on SQLite to avoid stale snapshots."""
        if self.db.get_bind().dialect.name == "sqlite":
            if self.db.in_transaction():
                raise PriceIntentUnavailable(_UNAVAILABLE)
            try:
                self.db.execute(text("UPDATE doctor_price_generation_clock SET value=value WHERE 0"))
            except DBAPIError as exc:
                _raise_database_error(exc)
            self._sqlite_writer = True
            self._transaction = self.db.get_transaction()

    def pin_trusted_schema(self) -> None:
        """Pin trusted PG schema before any actor/clinical reads in this transaction.

        Schema and owner must be anchored by trusted deployment configuration;
        owner-role membership must be reviewed there.
        """
        if self.db.get_bind().dialect.name == "sqlite":
            return
        if self.db.get_bind().dialect.name != "postgresql":
            raise PriceIntentUnavailable(_UNAVAILABLE)
        try:
            self.db.connection()
            dialect = self.db.get_bind().dialect
            schema = self.schema
            owner = self.schema_owner
            for value in (schema, owner):
                if not isinstance(value, str) or not value or "\x00" in value:
                    raise PriceIntentUnavailable(_UNAVAILABLE)
                try:
                    if len(value.encode("utf-8")) > 63:
                        raise PriceIntentUnavailable(_UNAVAILABLE)
                except UnicodeError:
                    raise PriceIntentUnavailable(_UNAVAILABLE) from None
            safe = self.db.execute(text("""
                SELECT EXISTS (
                  SELECT 1 FROM pg_catalog.pg_namespace n
                  JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner
                  WHERE n.nspname=:schema AND r.rolname=:owner
                    AND NOT EXISTS (
                      SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
                      WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner
                    )
                )
            """), {"schema": schema, "owner": owner}).scalar_one()
            if not safe:
                raise PriceIntentUnavailable(_UNAVAILABLE)
            quoted = dialect.identifier_preparer.quote_schema(schema)
            self.db.execute(text("SELECT pg_catalog.set_config('search_path', :path, true)"),
                            {"path": f"pg_catalog, {quoted}, pg_temp"})
            self._schema_transaction = self.db.get_transaction()
        except DBAPIError as exc:
            _raise_database_error(exc)

    def lock_actor_scope(self, actor_id: int, operation: str) -> None:
        """After User locks, before Doctor/Visit/Service locks; all issuers must use it."""
        if type(actor_id) is not int or actor_id < 1 or operation not in _OPERATIONS:
            raise PriceIntentInvalid(_INVALID)
        dialect = self.db.get_bind().dialect.name
        if dialect == "sqlite":
            if not self._sqlite_writer or self._transaction is not self.db.get_transaction():
                raise PriceIntentUnavailable(_UNAVAILABLE)
        elif dialect == "postgresql":
            if self._schema_transaction is None or self._schema_transaction is not self.db.get_transaction():
                raise PriceIntentUnavailable(_UNAVAILABLE)
            try:
                acquired = self.db.execute(
                    text("SELECT pg_catalog.pg_try_advisory_xact_lock(pg_catalog.hashtextextended(:scope, 0))"),
                    {"scope": f"doctor-price:v1:{actor_id}:{operation}"},
                ).scalar_one()
                if not acquired:
                    raise PriceIntentPending(_CONFLICT)
            except DBAPIError as exc:
                _raise_database_error(exc)
            self._transaction = self.db.get_transaction()
        else:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        self._scope = (actor_id, operation)

    def _require_scope(self, actor_id: int | None = None, operation: str | None = None) -> tuple[int, str]:
        if (not self._scope or self._transaction is not self.db.get_transaction()
                or self._registry_transaction is not self.db.get_transaction()):
            raise PriceIntentUnavailable(_UNAVAILABLE)
        if actor_id is not None and self._scope != (actor_id, operation):
            raise PriceIntentUnavailable(_UNAVAILABLE)
        return self._scope

    def _ensure_full_visibility(self) -> None:
        if self.db.get_bind().dialect.name != "postgresql":
            return
        if self._schema_transaction is None or self._schema_transaction is not self.db.get_transaction():
            self.pin_trusted_schema()
        if not isinstance(self.runtime_role, str) or not self.runtime_role or "\x00" in self.runtime_role:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        # DDL/ACL deployment changes must happen with traffic drained. These
        # ACCESS SHARE locks additionally serialize ordinary policy/table DDL.
        names = ("doctor_price_hmac_key_versions", "doctor_price_intents", "doctor_price_intent_keys", "doctor_price_intent_lines")
        quote = self.db.get_bind().dialect.identifier_preparer.quote_identifier
        schema = quote(self.schema)
        self.db.execute(text("LOCK TABLE " + ", ".join(f"{schema}.{quote(name)}" for name in names) + " IN ACCESS SHARE MODE"))
        actor = self.db.execute(text("""
            SELECT r.oid,r.rolname,r.rolcanlogin,r.rolsuper,r.rolbypassrls,
                   r.rolcreaterole,r.rolcreatedb,r.rolreplication,
                   current_user AS current_name, session_user AS login_name
            FROM pg_catalog.pg_roles r WHERE r.rolname=:role
        """), {"role": self.runtime_role}).mappings().first()
        if (actor is None or actor["current_name"] != self.runtime_role or actor["login_name"] != self.runtime_role
            or not actor["rolcanlogin"] or any(actor[name] for name in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))):
            raise PriceIntentUnavailable(_UNAVAILABLE)
        oid = actor["oid"]
        memberships = self.db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=:oid)
        """), {"oid": oid}).scalar_one()
        if memberships:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        schema_owner = self.db.execute(text("""
            SELECT n.nspowner,r.rolcanlogin,r.rolsuper FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname=:schema
        """), {"schema": self.schema}).mappings().one()
        if schema_owner["nspowner"] == oid or (schema_owner["rolcanlogin"] and not schema_owner["rolsuper"]):
            raise PriceIntentUnavailable(_UNAVAILABLE)
        tables = self.db.execute(text("""
            SELECT c.oid,c.relname,c.relowner,c.relrowsecurity,r.rolcanlogin,r.rolsuper
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
            WHERE n.nspname=:schema AND c.relname=ANY(:names) AND c.relkind IN ('r','p')
        """), {"schema": self.schema, "names": list(names)}).mappings().all()
        if len(tables) != len(names) or len({row["relowner"] for row in tables}) != 1:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        owner_oid = tables[0]["relowner"]
        owner_members = self.db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
              WHERE NOT r.rolsuper AND r.oid NOT IN (:schema_owner,:table_owner)
                AND (pg_catalog.pg_has_role(r.oid,:schema_owner,'MEMBER')
                     OR pg_catalog.pg_has_role(r.oid,:table_owner,'MEMBER')))
        """), {"schema_owner": schema_owner["nspowner"], "table_owner": owner_oid}).scalar_one()
        if owner_members:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        for table in tables:
            if (not table["relrowsecurity"] or table["relowner"] == oid
                or (table["rolcanlogin"] and not table["rolsuper"])):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            table_oid = table["oid"]
            policies = self.db.execute(text("""
                SELECT p.polname,p.polcmd,p.polpermissive,p.polroles,
                       pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS qual,
                       pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS checked
                FROM pg_catalog.pg_policy p WHERE p.polrelid=:oid
            """), {"oid": table_oid}).mappings().all()
            expected = {
                "doctor_price_template_select": ("r", table["relowner"], "true", None),
                "doctor_price_template_insert": ("a", table["relowner"], None, "true"),
                "doctor_price_backend_select": ("r", oid, "true", None),
                "doctor_price_backend_insert": ("a", oid, None, "true"),
            }
            if len(policies) != len(expected):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            for policy in policies:
                shape = expected.get(policy["polname"])
                if (shape is None or not policy["polpermissive"] or
                    (policy["polcmd"], policy["polroles"], policy["qual"], policy["checked"]) !=
                    (shape[0], [shape[1]], shape[2], shape[3])):
                    raise PriceIntentUnavailable(_UNAVAILABLE)
            acl = self.db.execute(text("""
                SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_class c,
                  LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
                WHERE c.oid=:oid
            """), {"oid": table_oid}).mappings().all()
            if any(row["grantee"] != table["relowner"] and not
                   (row["grantee"] == oid and row["privilege_type"] in {"SELECT", "INSERT"} and not row["is_grantable"])
                   for row in acl):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            columns = self.db.execute(text("""
                SELECT a.grantee FROM pg_catalog.pg_attribute c,
                  LATERAL pg_catalog.aclexplode(c.attacl) a
                WHERE c.attrelid=:oid AND c.attnum>0 AND NOT c.attisdropped
            """), {"oid": table_oid}).scalars().all()
            if any(grantee != table["relowner"] for grantee in columns):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            privileges = self.db.execute(text("""
                SELECT pg_catalog.has_table_privilege(:role,:oid,'SELECT') AS can_read,
                       pg_catalog.has_table_privilege(:role,:oid,'INSERT') AS can_insert,
                       pg_catalog.has_table_privilege(:role,:oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS dangerous,
                       pg_catalog.has_any_column_privilege(:role,:oid,'UPDATE,REFERENCES') AS dangerous_columns
            """), {"role": self.runtime_role, "oid": table_oid}).mappings().one()
            if not privileges["can_read"] or not privileges["can_insert"] or privileges["dangerous"] or privileges["dangerous_columns"]:
                raise PriceIntentUnavailable(_UNAVAILABLE)
            if table["relname"] != "doctor_price_hmac_key_versions":
                qualified = f"{schema}.{quote(table['relname'])}"
                sequence = self.db.execute(text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"), {"table": qualified}).scalar_one()
                if sequence is None:
                    raise PriceIntentUnavailable(_UNAVAILABLE)
                perms = self.db.execute(text("""
                    SELECT pg_catalog.has_sequence_privilege(:role,:seq,'USAGE') AS can_use,
                           pg_catalog.has_sequence_privilege(:role,:seq,'UPDATE') AS can_reset
                """), {"role": self.runtime_role, "seq": sequence}).mappings().one()
                if not perms["can_use"] or perms["can_reset"]:
                    raise PriceIntentUnavailable(_UNAVAILABLE)
                seq_acl = self.db.execute(text("""
                    SELECT a.grantee,a.privilege_type,a.is_grantable,c.relowner FROM pg_catalog.pg_class c,
                      LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('S',c.relowner))) a
                    WHERE c.oid=pg_catalog.to_regclass(:sequence)
                """), {"sequence": sequence}).mappings().all()
                if not seq_acl or any(row["grantee"] != row["relowner"] and not
                    (row["grantee"] == oid and row["privilege_type"] == "USAGE" and not row["is_grantable"])
                    for row in seq_acl):
                    raise PriceIntentUnavailable(_UNAVAILABLE)
        self.db.execute(text("SET LOCAL row_security = on"))

    def verify_registry(self, *, register_active: bool) -> None:
        """Verify active and every version referenced by durable intents.

        The read-only mode never registers a key. Registration is transactional;
        callers, including the explicit operator CLI, own commit and rollback.
        """
        try:
            self._ensure_full_visibility()
            active = self.keyring.active_version
            if register_active and self.db.get_bind().dialect.name == "sqlite" and (
                not self._sqlite_writer or self._transaction is not self.db.get_transaction()
            ):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            rows = self.db.execute(text("SELECT version,key_check_digest FROM doctor_price_hmac_key_versions")).all()
            registry = {row.version: row.key_check_digest for row in rows}
            used = set(self.db.execute(text("""
                SELECT fingerprint_version FROM doctor_price_intents
                UNION SELECT issued_confirmation_digest_version FROM doctor_price_intents
                WHERE issued_confirmation_digest_version IS NOT NULL
            """)).scalars())
            if not used.issubset(registry):
                raise PriceIntentUnavailable(_UNAVAILABLE)
            for version in used | ({active} if active in registry else set()):
                if not hmac.compare_digest(registry[version], self.keyring.commitment(version)):
                    raise PriceIntentUnavailable(_UNAVAILABLE)
            if active not in registry:
                if not register_active:
                    raise PriceIntentUnavailable(_UNAVAILABLE)
                sql = "INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (:version,:digest)"
                if self.db.get_bind().dialect.name == "postgresql":
                    sql += " ON CONFLICT (version) DO NOTHING"
                self.db.execute(text(sql), {"version": active, "digest": self.keyring.commitment(active)})
                observed = self.db.execute(text("SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=:v"), {"v": active}).scalar_one_or_none()
                if observed is None or not hmac.compare_digest(observed, self.keyring.commitment(active)):
                    raise PriceIntentUnavailable(_UNAVAILABLE)
            self._registry_transaction = self.db.get_transaction()
        except DBAPIError as exc:
            _raise_database_error(exc)

    def fingerprint(self, canonical: Any, *, version: int | None = None) -> tuple[int, str]:
        actor_id, operation = self._require_scope()
        chosen = self.keyring.active_version if version is None else version
        payload = _canonical({"actor_id": actor_id, "operation": operation, "request": canonical})
        return chosen, self.keyring._digest(chosen, b"intent", payload)

    def confirmation_digest(self, token: str, version: int | None = None) -> tuple[int, str]:
        self._require_scope()
        if not isinstance(token, str) or not 1 <= len(token) <= 512:
            raise PriceIntentInvalid(_INVALID)
        chosen = self.keyring.active_version if version is None else version
        try:
            value = token.encode("utf-8")
        except UnicodeError:
            raise PriceIntentInvalid(_INVALID) from None
        return chosen, self.keyring._digest(chosen, b"confirmation", value)

    def lookup(
        self, actor_id: int, operation: str, canonical: Any,
        client_key: str | None, now: datetime | None = None, *, mode: str | None = None,
    ) -> LookupResult:
        """Find a durable result without relying on a wall-clock dedup window.

        Known keys always bind to the exact original intent. An unknown key
        with mode=new starts a deliberate new operation; mode=retry may bind
        only to one matching earlier result after caller authorization. An
        unkeyed collision or omitted mode on a conflicting new key is an
        explicit ambiguity, never a successful replay or an automatic write.
        """
        self._require_scope(actor_id, operation)
        if mode not in (None, "retry", "new") or (client_key is None and mode is not None):
            raise PriceIntentInvalid(_INVALID)
        alias = _key_hash(client_key) if client_key is not None else None
        if alias is not None:
            row = self.db.execute(text("""
                SELECT i.id,i.fingerprint_version,i.fingerprint FROM doctor_price_intent_keys k
                JOIN doctor_price_intents i ON i.id=k.intent_id
                WHERE k.actor_user_id_snapshot=:actor AND k.operation=:op AND k.key_hash=:key
            """), {"actor": actor_id, "op": operation, "key": alias}).first()
            if row:
                if not hmac.compare_digest(row.fingerprint, self.fingerprint(canonical, version=row.fingerprint_version)[1]):
                    raise PriceIntentConflict(_CONFLICT)
                return LookupResult(row.id)
            if mode == "new":
                return LookupResult(None)
        # Search every durable fingerprint version, not a mutable Visit date or
        # wall clock. The compound index makes this bounded per version.
        versions = self.db.execute(text("""
            SELECT DISTINCT fingerprint_version FROM doctor_price_intents
            WHERE actor_user_id_snapshot=:actor AND operation=:op
        """), {"actor": actor_id, "op": operation}).scalars().all()
        if len(versions) > 256:
            raise PriceIntentUnavailable(_UNAVAILABLE)
        matches: list[int] = []
        for version in versions:
            digest = self.fingerprint(canonical, version=version)[1]
            rows = self.db.execute(text("""
                SELECT id FROM doctor_price_intents
                WHERE actor_user_id_snapshot=:actor AND operation=:op
                  AND fingerprint_version=:version AND fingerprint=:digest
                ORDER BY id LIMIT 2
            """), {"actor": actor_id, "op": operation, "version": version, "digest": digest}).scalars().all()
            matches.extend(rows)
            if len(matches) > 1:
                raise PriceIntentAmbiguous(_CONFLICT)
        if not matches:
            if mode == "retry":
                raise PriceIntentConflict(_CONFLICT)
            return LookupResult(None)
        if client_key is None or mode is None:
            raise PriceIntentAmbiguous(_CONFLICT)
        return LookupResult(matches[0], needs_alias=True)

    def bind_alias(self, actor_id: int, operation: str, intent_id: int, client_key: str) -> None:
        """Only call after current actor and live result have been reauthorized."""
        self._require_scope(actor_id, operation)
        if type(intent_id) is not int or intent_id < 1:
            raise PriceIntentInvalid(_INVALID)
        try:
            result = self.db.execute(text("""
                INSERT INTO doctor_price_intent_keys (intent_id,actor_user_id_snapshot,operation,key_hash)
                VALUES (:intent,:actor,:op,:key)
                ON CONFLICT (actor_user_id_snapshot,operation,key_hash) DO NOTHING
            """), {"intent": intent_id, "actor": actor_id, "op": operation, "key": _key_hash(client_key)})
            if result.rowcount != 1:
                raise PriceIntentConflict(_CONFLICT)
        except DBAPIError as exc:
            _raise_database_error(exc, conflict=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or provision doctor-price key commitments.")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--check-keyring", action="store_true")
    options.add_argument("--register-active", action="store_true")
    args = parser.parse_args()
    previous_log_level = logging.root.manager.disable
    ready = False
    try:
        # The development settings fallback may create a secret file. A
        # read-only operational check requires the JWT secret to be explicitly
        # provisioned in the process environment as it is in production.
        if not os.environ.get("SECRET_KEY"):
            raise PriceIntentUnavailable(_UNAVAILABLE)
        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from app.core.config import settings
            from app.db.session import SessionLocal

            keyring = PriceIntentKeyring.from_settings(settings)
            with SessionLocal() as db:
                service = DoctorPriceIntentService(db, keyring, settings.DOCTOR_PRICE_DB_SCHEMA,
                                                   settings.DOCTOR_PRICE_DB_SCHEMA_OWNER)
                if args.register_active:
                    service.reserve_sqlite_writer()
                service.pin_trusted_schema()
                service.verify_registry(register_active=args.register_active)
                if args.register_active:
                    db.commit()
            ready = True
    except Exception:
        # No exception string, database URL, key or commitment is displayed.
        pass
    finally:
        logging.disable(previous_log_level)
    print("Doctor price keyring is ready" if ready else "Doctor price keyring is unavailable")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
