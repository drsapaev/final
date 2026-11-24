"""Pin the financial schema before the audited authentication dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.trusted_schema import TrustedSchemaUnavailable, pin_application_schema
from app.models.user import User


async def _authenticate(
    token: str, db: Session, roles: tuple[str, ...],
) -> User:
    """Use one session for preflight, authentication, role check and route."""
    try:
        if db.get_bind().dialect.name == "postgresql":
            # A fresh SQLAlchemy engine discovers default_schema_name only on
            # its first connection. Do that before comparing the trusted anchor;
            # no application relation or identity has been read at this point.
            db.connection()
            schema = settings.TRUSTED_DB_SCHEMA
            owner = settings.TRUSTED_DB_SCHEMA_OWNER
            if (schema != db.get_bind().dialect.default_schema_name
                    or (settings.DOCTOR_PRICE_DB_SCHEMA is not None and settings.DOCTOR_PRICE_DB_SCHEMA != schema)
                    or (settings.DOCTOR_PRICE_DB_SCHEMA_OWNER is not None and settings.DOCTOR_PRICE_DB_SCHEMA_OWNER != owner)
                    or (settings.INVITATION_DB_SCHEMA is not None and settings.INVITATION_DB_SCHEMA != schema)
                    or (settings.INVITATION_DB_SCHEMA_OWNER is not None and settings.INVITATION_DB_SCHEMA_OWNER != owner)):
                raise TrustedSchemaUnavailable("Trusted database schema unavailable")
        pin_application_schema(
            db, schema=settings.TRUSTED_DB_SCHEMA,
            expected_owner=settings.TRUSTED_DB_SCHEMA_OWNER,
            expected_runtime_role=settings.TRUSTED_DB_RUNTIME_ROLE,
            trusted_owner_members=settings.TRUSTED_DB_OWNER_MEMBERS,
            expected_auth_owner=settings.TRUSTED_AUTH_TABLE_OWNER,
            trusted_auth_owner_members=settings.TRUSTED_AUTH_OWNER_MEMBERS,
            trusted_auth_read_roles=settings.TRUSTED_AUTH_READ_ROLES,
            trusted_auth_write_roles=settings.TRUSTED_AUTH_WRITE_ROLES,
            expected_users_owner=settings.TRUSTED_AUTH_USERS_OWNER,
            trusted_users_owner_members=settings.TRUSTED_AUTH_USERS_OWNER_MEMBERS,
            trusted_users_write_roles=settings.TRUSTED_AUTH_USERS_WRITE_ROLES,
        )
    except (TrustedSchemaUnavailable, SQLAlchemyError):
        db.rollback()
        raise HTTPException(status_code=503, detail="Проверка доступа временно недоступна") from None

    actor = await deps.get_current_user(token=token, db=db)
    role_checked = deps.require_roles(*roles)(current_user=actor, db=db)
    return deps.require_active_roles(*roles)(current_user=actor, db=db, _role_gated=role_checked)


async def financial_reviewer(
    token: str = Depends(deps.oauth2_scheme), db: Session = Depends(deps.get_db),
) -> User:
    return await _authenticate(token, db, ("Admin", "SuperAdmin", "Registrar"))


async def financial_admin(
    token: str = Depends(deps.oauth2_scheme), db: Session = Depends(deps.get_db),
) -> User:
    return await _authenticate(token, db, ("Admin", "SuperAdmin"))
