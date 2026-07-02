from __future__ import annotations

import logging
from collections.abc import Iterable
from enum import StrEnum

logger = logging.getLogger(__name__)


class DomainContext(StrEnum):
    PATIENT = "patient"
    SCHEDULING = "scheduling"
    QUEUE = "queue"
    BILLING = "billing"
    EMR = "emr"
    IAM = "iam"


_CONTEXT_PREFIXES: dict[DomainContext, tuple[str, ...]] = {
    DomainContext.PATIENT: (
        "app.services.patients_",
        "app.services.patient_",
        "app.repositories.patients_",
        "app.repositories.patient_",
        "app.models.patient",
        "app.models.family_relation",
        "app.models.user_profile",
    ),
    DomainContext.SCHEDULING: (
        "app.services.appointment",
        "app.services.schedule_",
        "app.services.morning_assignment",
        "app.repositories.appointment",
        "app.repositories.schedule_",
        "app.repositories.morning_assignment",
        "app.models.appointment",
        "app.models.schedule",
    ),
    DomainContext.QUEUE: (
        "app.services.queue_",
        "app.services.queues_",
        "app.services.online_queue_",
        "app.services.qr_queue_",
        "app.services.display_websocket",
        "app.services.board_",
        "app.repositories.queue_",
        "app.repositories.queues_",
        "app.repositories.online_queue_",
        "app.repositories.qr_queue_",
        "app.repositories.display_websocket_",
        "app.repositories.board_",
        "app.models.online_queue",
        "app.models.queue_profile",
        "app.models.display_config",
        "app.models.online",
    ),
    DomainContext.BILLING: (
        "app.services.billing_",
        "app.services.cashier_",
        "app.services.payment",
        "app.services.dynamic_pricing_",
        "app.services.discount_benefits_",
        "app.repositories.billing_",
        "app.repositories.cashier_",
        "app.repositories.payment",
        "app.repositories.dynamic_pricing_",
        "app.repositories.discount_benefits_",
        "app.models.billing",
        "app.models.payment",
        "app.models.payment_webhook",
        "app.models.payment_invoice",
        "app.models.refund_deposit",
        "app.models.dynamic_pricing",
        "app.models.discount_benefits",
    ),
    DomainContext.EMR: (
        "app.services.emr_",
        "app.services.dental_",
        "app.services.derma_",
        "app.services.cardio_",
        "app.services.visit_",
        "app.services.section_templates_",
        "app.services.doctor_templates_",
        "app.repositories.emr_",
        "app.repositories.dental_",
        "app.repositories.derma_",
        "app.repositories.cardio_",
        "app.repositories.visit_",
        "app.repositories.section_templates_",
        "app.repositories.doctor_templates_",
        "app.models.emr",
        "app.models.emr_v2",
        "app.models.emr_version",
        "app.models.emr_template",
        "app.models.visit",
        "app.models.odontogram",
        "app.models.dermatology_photos",
        "app.models.ecg_data",
        "app.models.doctor_templates",
        "app.models.section_templates",
    ),
    DomainContext.IAM: (
        "app.services.auth_",
        "app.services.authentication_",
        "app.services.roles_",
        "app.services.group_permissions_",
        "app.services.two_factor_",
        "app.services.security_management_",
        "app.services.token_blacklist_",
        "app.repositories.auth_",
        "app.repositories.authentication_",
        "app.repositories.roles_",
        "app.repositories.group_permissions_",
        "app.repositories.two_factor_",
        "app.repositories.security_management_",
        "app.models.user",
        "app.models.authentication",
        "app.models.role_permission",
        "app.models.two_factor_auth",
    ),
}


_ALLOWED_OUTBOUND: dict[DomainContext, set[DomainContext]] = {
    DomainContext.PATIENT: {DomainContext.IAM},
    DomainContext.SCHEDULING: {
        DomainContext.PATIENT,
        DomainContext.QUEUE,
        DomainContext.BILLING,
        DomainContext.IAM,
    },
    DomainContext.QUEUE: {
        DomainContext.PATIENT,
        DomainContext.SCHEDULING,
        DomainContext.BILLING,
        DomainContext.IAM,
    },
    DomainContext.BILLING: {
        DomainContext.PATIENT,
        DomainContext.SCHEDULING,
        DomainContext.QUEUE,
        DomainContext.IAM,
    },
    DomainContext.EMR: {
        DomainContext.PATIENT,
        DomainContext.SCHEDULING,
        DomainContext.BILLING,
        DomainContext.IAM,
    },
    DomainContext.IAM: set(),
}


def detect_context(module_name: str) -> DomainContext | None:
    """Resolve a Python module import path to a domain context."""
    for context, prefixes in _CONTEXT_PREFIXES.items():
        if module_name.startswith(prefixes):
            logger.debug(
                "context_registry.detect_context matched: module=%s context=%s",
                module_name,
                context.value,
            )
            return context
    logger.debug(
        "context_registry.detect_context unmatched: module=%s",
        module_name,
    )
    return None


def build_context_index(module_names: Iterable[str]) -> dict[str, DomainContext | None]:
    """Build `module -> context` mapping for architecture tests."""
    index: dict[str, DomainContext | None] = {}
    for module_name in module_names:
        context = detect_context(module_name)
        index[module_name] = context
        logger.debug(
            "context_registry.build_context_index item: module=%s context=%s",
            module_name,
            context.value if context else "none",
        )
    return index


def is_allowed_outbound_dependency(
    caller_context: DomainContext,
    target_context: DomainContext,
) -> bool:
    """Check if caller context can depend on target context."""
    if caller_context == target_context:
        logger.debug(
            "context_registry.outbound allowed (same context): caller=%s target=%s",
            caller_context.value,
            target_context.value,
        )
        return True

    allowed = target_context in _ALLOWED_OUTBOUND[caller_context]
    logger.debug(
        "context_registry.outbound check: caller=%s target=%s allowed=%s",
        caller_context.value,
        target_context.value,
        allowed,
    )
    return allowed


def validate_module_dependency(
    caller_module: str,
    imported_module: str,
) -> tuple[bool, str | None]:
    """
    Validate dependency direction between modules.

    Returns:
        (True, None) when dependency is allowed or out of domain scope.
        (False, reason) when dependency breaks context boundary rules.
    """
    caller_context = detect_context(caller_module)
    target_context = detect_context(imported_module)

    if caller_context is None or target_context is None:
        logger.debug(
            "context_registry.validate skipped: caller=%s target=%s reason=unknown-context",
            caller_module,
            imported_module,
        )
        return True, None

    if is_allowed_outbound_dependency(caller_context, target_context):
        logger.debug(
            "context_registry.validate allowed: caller=%s target=%s",
            caller_module,
            imported_module,
        )
        return True, None

    reason = (
        f"Forbidden context dependency: {caller_context.value} -> {target_context.value} "
        f"(caller={caller_module}, target={imported_module})"
    )
    logger.debug("context_registry.validate rejected: %s", reason)
    return False, reason


def get_context_prefixes() -> dict[DomainContext, tuple[str, ...]]:
    """Expose immutable-like view for tests and checks."""
    return {context: tuple(prefixes) for context, prefixes in _CONTEXT_PREFIXES.items()}

