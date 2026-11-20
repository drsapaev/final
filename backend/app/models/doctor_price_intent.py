"""Durable doctor price intent/result schema; not an authorization protocol.

Snapshots are audit data and must never restore a deleted live reference.
Producers must serialize, reauthorize, commit before replying and consumers
must revalidate the entire financial context before changing a price.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base


# Exact snapshots are evidence, never a substitute for live authorization.
_DOCTOR_BINDING = (
    "(doctor_id_snapshot IS NULL AND doctor_id IS NULL AND price_owner_generation IS NULL "
    "AND doctor_owner_user_id_snapshot IS NULL AND doctor_owner_user_id IS NULL AND doctor_user_auth_epoch IS NULL) OR "
    "(doctor_id_snapshot IS NOT NULL AND doctor_id_snapshot > 0 AND price_owner_generation IS NOT NULL AND price_owner_generation > 0 "
    "AND (doctor_id IS NULL OR doctor_id = doctor_id_snapshot) AND ("
    "(doctor_owner_user_id_snapshot IS NULL AND doctor_owner_user_id IS NULL AND doctor_user_auth_epoch IS NULL) OR "
    "(doctor_owner_user_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot > 0 AND "
    "(doctor_owner_user_id IS NULL OR doctor_owner_user_id = doctor_owner_user_id_snapshot) AND "
    "doctor_user_auth_epoch IS NOT NULL AND doctor_user_auth_epoch >= 0)))"
)
_CONFIRMATION_BINDING = (
    "(issued_confirmation_epoch IS NULL AND issued_confirmation_digest IS NULL AND issued_confirmation_digest_version IS NULL AND issued_confirmation_expires_at IS NULL) OR "
    "(operation = 'schedule_next' AND issued_confirmation_epoch IS NOT NULL AND issued_confirmation_epoch > 0 AND issued_confirmation_digest IS NOT NULL AND length(issued_confirmation_digest) = 64 AND issued_confirmation_digest_version IS NOT NULL AND issued_confirmation_digest_version > 0 AND issued_confirmation_expires_at IS NOT NULL)"
)
_SQLITE_INTEGERS = (
    "typeof(actor_user_id_snapshot)='integer' AND typeof(actor_user_auth_epoch)='integer' AND typeof(patient_id_snapshot)='integer' AND typeof(visit_id_snapshot)='integer' AND typeof(fingerprint_version)='integer' AND "
    "(doctor_id_snapshot IS NULL OR typeof(doctor_id_snapshot)='integer') AND (price_owner_generation IS NULL OR typeof(price_owner_generation)='integer') AND "
    "(doctor_owner_user_id_snapshot IS NULL OR typeof(doctor_owner_user_id_snapshot)='integer') AND (doctor_user_auth_epoch IS NULL OR typeof(doctor_user_auth_epoch)='integer') AND "
    "(issued_confirmation_epoch IS NULL OR typeof(issued_confirmation_epoch)='integer') AND (issued_confirmation_digest_version IS NULL OR typeof(issued_confirmation_digest_version)='integer')"
)


class DoctorPriceHmacKeyVersion(Base):
    """Immutable commitment, never key material; migration enforces immutability."""
    __tablename__ = "doctor_price_hmac_key_versions"
    __table_args__ = (
        CheckConstraint("version > 0 AND length(key_check_digest) = 64", name="ck_doctor_price_hmac_key_value"),
        CheckConstraint("typeof(version)='integer' AND key_check_digest NOT GLOB '*[^0-9a-f]*'", name="ck_doctor_price_hmac_key_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("key_check_digest ~ '^[0-9a-f]{64}$'", name="ck_doctor_price_hmac_key_pg").ddl_if(dialect="postgresql"),
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_check_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DoctorPriceIntent(Base):
    __tablename__ = "doctor_price_intents"
    __table_args__ = (
        UniqueConstraint("id", "actor_user_id_snapshot", "operation", name="uq_doctor_price_intent_identity"),
        Index("ix_doctor_price_intent_recent", "actor_user_id_snapshot", "operation", "created_at"),
        Index("ix_doctor_price_intent_fingerprint", "actor_user_id_snapshot", "operation", "fingerprint_version", "fingerprint"),
        CheckConstraint("operation IN ('schedule_next', 'add_service')", name="ck_doctor_price_intent_operation"),
        CheckConstraint("requester_type IN ('doctor', 'admin') AND actor_user_auth_epoch >= 0", name="ck_doctor_price_intent_requester"),
        CheckConstraint("actor_user_id_snapshot > 0 AND (actor_user_id IS NULL OR actor_user_id = actor_user_id_snapshot)", name="ck_doctor_price_intent_actor"),
        CheckConstraint("patient_id_snapshot > 0 AND (patient_id IS NULL OR patient_id = patient_id_snapshot)", name="ck_doctor_price_intent_patient"),
        CheckConstraint("visit_id_snapshot > 0 AND (visit_id IS NULL OR visit_id = visit_id_snapshot)", name="ck_doctor_price_intent_visit"),
        CheckConstraint(_DOCTOR_BINDING, name="ck_doctor_price_intent_doctor"),
        CheckConstraint("requester_type <> 'doctor' OR (doctor_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot IS NOT NULL AND doctor_owner_user_id_snapshot = actor_user_id_snapshot)", name="ck_doctor_price_intent_doctor_requester"),
        CheckConstraint(_CONFIRMATION_BINDING, name="ck_doctor_price_intent_confirmation"),
        CheckConstraint(_SQLITE_INTEGERS, name="ck_doctor_price_intent_integers_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("fingerprint_version > 0 AND length(fingerprint) = 64", name="ck_doctor_price_intent_hash_length"),
        CheckConstraint("fingerprint NOT GLOB '*[^0-9a-f]*' AND (issued_confirmation_digest IS NULL OR issued_confirmation_digest NOT GLOB '*[^0-9a-f]*')", name="ck_doctor_price_intent_hash_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$' AND (issued_confirmation_digest IS NULL OR issued_confirmation_digest ~ '^[0-9a-f]{64}$')", name="ck_doctor_price_intent_hash_pg").ddl_if(dialect="postgresql"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    requester_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_auth_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id", ondelete="SET NULL"))
    doctor_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    doctor_owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    doctor_owner_user_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    doctor_user_auth_epoch: Mapped[int | None] = mapped_column(BigInteger)
    price_owner_generation: Mapped[int | None] = mapped_column(BigInteger)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visits.id", ondelete="SET NULL"))
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint_version: Mapped[int] = mapped_column(Integer, ForeignKey("doctor_price_hmac_key_versions.version", ondelete="RESTRICT"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_confirmation_epoch: Mapped[int | None] = mapped_column(BigInteger)
    issued_confirmation_digest: Mapped[str | None] = mapped_column(String(64))
    issued_confirmation_digest_version: Mapped[int | None] = mapped_column(Integer, ForeignKey("doctor_price_hmac_key_versions.version", ondelete="RESTRICT"))
    issued_confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DoctorPriceIntentKey(Base):
    """Stable, non-authoritative key aliases; never persist the raw key."""
    __tablename__ = "doctor_price_intent_keys"
    __table_args__ = (
        UniqueConstraint("actor_user_id_snapshot", "operation", "key_hash", name="uq_doctor_price_intent_alias"),
        ForeignKeyConstraint(
            ["intent_id", "actor_user_id_snapshot", "operation"],
            ["doctor_price_intents.id", "doctor_price_intents.actor_user_id_snapshot", "doctor_price_intents.operation"],
            name="fk_doctor_price_intent_alias_identity", ondelete="RESTRICT",
        ),
        CheckConstraint("actor_user_id_snapshot > 0 AND operation IN ('schedule_next', 'add_service') AND length(key_hash) = 64", name="ck_doctor_price_intent_alias_value"),
        CheckConstraint("typeof(actor_user_id_snapshot)='integer' AND typeof(intent_id)='integer' AND key_hash NOT GLOB '*[^0-9a-f]*'", name="ck_doctor_price_intent_alias_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name="ck_doctor_price_intent_alias_pg").ddl_if(dialect="postgresql"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DoctorPriceIntentLine(Base):
    __tablename__ = "doctor_price_intent_lines"
    __table_args__ = (
        UniqueConstraint("intent_id", "ordinal", name="uq_doctor_price_intent_line_ordinal"),
        CheckConstraint("typeof(ordinal) = 'integer' AND typeof(service_id_snapshot) = 'integer' AND typeof(qty) = 'integer' AND (raw_custom_minor IS NULL OR typeof(raw_custom_minor) = 'integer') AND typeof(baseline_minor) = 'integer' AND typeof(proposed_minor) = 'integer' AND typeof(visit_service_id_snapshot) = 'integer' AND (override_id_snapshot IS NULL OR typeof(override_id_snapshot) = 'integer')", name="ck_doctor_price_intent_line_integers_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("ordinal >= 0 AND service_id_snapshot > 0 AND qty BETWEEN 1 AND 2147483647", name="ck_doctor_price_intent_line_identity"),
        CheckConstraint("raw_custom_minor IS NULL OR raw_custom_minor BETWEEN 0 AND 999999999999", name="ck_doctor_price_intent_line_raw"),
        CheckConstraint("baseline_minor BETWEEN 0 AND 999999999999 AND proposed_minor BETWEEN 0 AND 999999999999", name="ck_doctor_price_intent_line_amount"),
        CheckConstraint("visit_service_id_snapshot > 0 AND (visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot)", name="ck_doctor_price_intent_line_target"),
        CheckConstraint("(override_id_snapshot IS NULL AND override_id IS NULL) OR (override_id_snapshot IS NOT NULL AND override_id_snapshot > 0 AND (override_id IS NULL OR override_id = override_id_snapshot))", name="ck_doctor_price_intent_line_override"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_id: Mapped[int] = mapped_column(ForeignKey("doctor_price_intents.id", ondelete="RESTRICT"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_custom_minor: Mapped[int | None] = mapped_column(BigInteger)
    baseline_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proposed_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visit_service_id: Mapped[int | None] = mapped_column(ForeignKey("visit_services.id", ondelete="SET NULL"))
    visit_service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    override_id: Mapped[int | None] = mapped_column(ForeignKey("doctor_price_overrides.id", ondelete="SET NULL"))
    override_id_snapshot: Mapped[int | None] = mapped_column(Integer)
