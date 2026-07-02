from __future__ import annotations

import logging
from typing import Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger

logger = logging.getLogger(__name__)


class AccessDecision(BaseModel):
    allowed: bool
    reason: str | None = None


class IamContract(Protocol):
    def check_permission(
        self,
        actor_user_id: int,
        permission_code: str,
        request_id: str | None = None,
    ) -> AccessDecision: ...

    def resolve_role_scope(
        self,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> list[str]: ...


class IamContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: IamContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "iam")

    def check_permission(
        self,
        actor_user_id: int,
        permission_code: str,
        request_id: str | None = None,
    ) -> AccessDecision:
        self._contract_logger.log_entry(
            "check_permission",
            request_id,
            actor_user_id=actor_user_id,
            permission_code=permission_code,
        )
        decision = self._contract.check_permission(
            actor_user_id=actor_user_id,
            permission_code=permission_code,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "check_permission",
            request_id,
            allowed=decision.allowed,
        )
        return decision

    def resolve_role_scope(
        self,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> list[str]:
        self._contract_logger.log_entry(
            "resolve_role_scope",
            request_id,
            actor_user_id=actor_user_id,
        )
        scopes = self._contract.resolve_role_scope(
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "resolve_role_scope",
            request_id,
            scope_count=len(scopes),
        )
        return scopes

