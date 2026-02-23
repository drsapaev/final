"""Domain contract interfaces and facade wrappers."""

from app.domain.contracts.billing_contracts import (
    BillingContract,
    BillingContractFacade,
    PaymentStatusSnapshot,
)
from app.domain.contracts.emr_contracts import (
    EmrContract,
    EmrContractFacade,
    VisitClinicalSnapshot,
)
from app.domain.contracts.iam_contracts import (
    AccessDecision,
    IamContract,
    IamContractFacade,
)
from app.domain.contracts.interoperability_contracts import (
    DmedCapabilityContract,
    EgovCapabilityContract,
    ExternalIntegrationContract,
    InsuranceCapabilityContract,
    IntegrationRegistryContract,
    IntegrationRegistryContractFacade,
)
from app.domain.contracts.patient_contracts import (
    PatientContract,
    PatientContractFacade,
    PatientSummary,
)
from app.domain.contracts.queue_contracts import (
    QueueContract,
    QueueContractFacade,
    QueueTokenSnapshot,
)
from app.domain.contracts.scheduling_contracts import (
    AppointmentSnapshot,
    SchedulingContract,
    SchedulingContractFacade,
)

__all__ = [
    "AccessDecision",
    "AppointmentSnapshot",
    "BillingContract",
    "BillingContractFacade",
    "DmedCapabilityContract",
    "EmrContract",
    "EmrContractFacade",
    "EgovCapabilityContract",
    "ExternalIntegrationContract",
    "IamContract",
    "IamContractFacade",
    "InsuranceCapabilityContract",
    "IntegrationRegistryContract",
    "IntegrationRegistryContractFacade",
    "PatientContract",
    "PatientContractFacade",
    "PatientSummary",
    "PaymentStatusSnapshot",
    "QueueContract",
    "QueueContractFacade",
    "QueueTokenSnapshot",
    "SchedulingContract",
    "SchedulingContractFacade",
    "VisitClinicalSnapshot",
]
