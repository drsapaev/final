"""ORM mapping for published public-site image metadata.

Image bytes remain outside the application checkout. This model mirrors the
existing ``public_site_media`` table; it does not add upload or delivery
behavior.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class PublicSiteMedia(Base):
    """Publication metadata for the clinic logo and doctor portraits."""

    __tablename__ = "public_site_media"
    __table_args__ = (
        CheckConstraint(
            "asset_kind IN ('clinic_logo', 'doctor_portrait')",
            name="ck_public_site_media_asset_kind",
        ),
        CheckConstraint(
            "(asset_kind = 'clinic_logo' AND doctor_id IS NULL) OR "
            "(asset_kind = 'doctor_portrait' AND doctor_id IS NOT NULL)",
            name="ck_public_site_media_owner",
        ),
        CheckConstraint(
            "storage_key ~ '^[0-9a-f]{64}$'",
            name="ck_public_site_media_storage_key_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_public_site_media_mime_type",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="ck_public_site_media_byte_size_positive",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_public_site_media_sha256_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "(is_published AND published_at IS NOT NULL) OR "
            "(NOT is_published AND published_at IS NULL)",
            name="ck_public_site_media_publication_state",
        ),
        PrimaryKeyConstraint("id", name="pk_public_site_media"),
        UniqueConstraint("storage_key", name="uq_public_site_media_storage_key"),
        Index(
            "uq_public_site_media_published_clinic_logo",
            "asset_kind",
            unique=True,
            postgresql_where=text(
                "asset_kind = 'clinic_logo' AND is_published IS TRUE"
            ),
            sqlite_where=text("asset_kind = 'clinic_logo' AND is_published IS TRUE"),
        ),
        Index(
            "uq_public_site_media_published_doctor_portrait",
            "doctor_id",
            unique=True,
            postgresql_where=text(
                "asset_kind = 'doctor_portrait' AND is_published IS TRUE"
            ),
            sqlite_where=text(
                "asset_kind = 'doctor_portrait' AND is_published IS TRUE"
            ),
        ),
        Index("ix_public_site_media_doctor_id", "doctor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    doctor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "doctors.id",
            name="fk_public_site_media_doctor_id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_public_site_media_uploaded_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
