from __future__ import annotations

import logging

from app.domain.contracts.iam_contracts import (
    AccessDecision,
    IamContract,
    IamContractFacade,
)


logger = logging.getLogger(__name__)


class IamServiceContractAdapter:
    """Adapter from legacy role model to IAM contract."""

    _PERMISSION_ROLE_MAP: dict[str, set[str]] = {
        "emr.write": {
            "admin",
            "doctor",
            "registrar",
            "cardio",
            "cardiology",
            "cardiologist",
            "derma",
            "dermatologist",
            "dentist",
            "lab",
            "laboratory",
        }
    }

    def __init__(self, actor) -> None:  # type: ignore[no-untyped-def]
        self._actor = actor

    def check_permission(
        self,
        actor_user_id: int,
        permission_code: str,
        request_id: str | None = None,
    ) -> AccessDecision:
        _ = request_id
        if getattr(self._actor, "id", None) != actor_user_id:
            return AccessDecision(
                allowed=False,
                reason="actor_mismatch",
            )

        allowed_roles = self._PERMISSION_ROLE_MAP.get(permission_code)
        if not allowed_roles:
            return AccessDecision(
                allowed=False,
                reason=f"permission_unknown:{permission_code}",
            )

        role_value = str(getattr(self._actor, "role", "") or "").strip().lower()
        return AccessDecision(
            allowed=role_value in allowed_roles,
            reason=None if role_value in allowed_roles else f"role_denied:{role_value}",
        )

    def resolve_role_scope(
        self,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> list[str]:
        _ = request_id
        if getattr(self._actor, "id", None) != actor_user_id:
            return []
        role_value = str(getattr(self._actor, "role", "") or "").strip().lower()
        return [role_value] if role_value else []


class IamContextFacade:
    """Public entry point for cross-context identity and access checks."""

    def __init__(self, contract: IamContract) -> None:
        self._contract = IamContractFacade(contract)

    def check_permission(
        self,
        actor_user_id: int,
        permission_code: str,
        correlation_id: str | None = None,
    ) -> AccessDecision:
        logger.info(
            "iam_facade.check_permission correlation_id=%s actor_user_id=%s permission_code=%s",
            correlation_id or "-",
            actor_user_id,
            permission_code,
        )
        try:
            return self._contract.check_permission(
                actor_user_id=actor_user_id,
                permission_code=permission_code,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "iam_facade.check_permission failed correlation_id=%s actor_user_id=%s permission_code=%s",
                correlation_id or "-",
                actor_user_id,
                permission_code,
            )
            raise

    def resolve_role_scope(
        self,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> list[str]:
        logger.info(
            "iam_facade.resolve_role_scope correlation_id=%s actor_user_id=%s",
            correlation_id or "-",
            actor_user_id,
        )
        try:
            return self._contract.resolve_role_scope(
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "iam_facade.resolve_role_scope failed correlation_id=%s actor_user_id=%s",
                correlation_id or "-",
                actor_user_id,
            )
            raise
