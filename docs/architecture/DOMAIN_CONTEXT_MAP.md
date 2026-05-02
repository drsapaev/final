# Domain Context Map

Status: draft for Phase 4 (`Domain Modules`)  
Last updated: 2026-02-22

## Purpose

This map defines bounded contexts for the clinic platform and the allowed cross-context dependency directions.  
Goal: keep the modular monolith stable by preventing direct internal coupling between unrelated domains.

## Canonical Contexts

| Context | Responsibility |
|---|---|
| `patient` | Patient identity, demographics, profile data, and longitudinal patient linkage. |
| `scheduling` | Appointment lifecycle, slot planning, registrar workflow before queue entry. |
| `queue` | Online/live queue state, token lifecycle, room/display board updates. |
| `billing` | Tariffs, invoices, payment initialization, webhooks, reconciliation, refunds. |
| `emr` | Clinical record lifecycle (visit notes, templates, specialty sections, history/audit linkage). |
| `iam` | Authentication, authorization, roles/permissions, security factors, access policy checks. |

## Ownership Map (Current Codebase)

## `patient`
- Owned models:
- `backend/app/models/patient.py`
- `backend/app/models/family_relation.py`
- `backend/app/models/user_profile.py` (patient-linked profile scenarios)
- Owned services:
- `backend/app/services/patients_api_service.py`
- `backend/app/services/patient_appointments_api_service.py`
- Owned repositories:
- `backend/app/repositories/patients_api_repository.py`
- `backend/app/repositories/patient_appointments_api_repository.py`

## `scheduling`
- Owned models:
- `backend/app/models/appointment.py`
- `backend/app/models/schedule.py`
- Owned services:
- `backend/app/services/appointments_api_service.py`
- `backend/app/services/schedule_api_service.py`
- `backend/app/services/appointment_flow_api_service.py`
- Owned repositories:
- `backend/app/repositories/appointments_api_repository.py`
- `backend/app/repositories/schedule_api_repository.py`
- `backend/app/repositories/appointment_flow_api_repository.py`

## `queue`
- Owned models:
- `backend/app/models/online_queue.py`
- `backend/app/models/queue_profile.py`
- `backend/app/models/display_config.py`
- Owned services:
- `backend/app/services/queue_api_service.py`
- `backend/app/services/online_queue_api_service.py`
- `backend/app/services/qr_queue_api_service.py`
- `backend/app/services/display_websocket.py`
- Owned repositories:
- `backend/app/repositories/queue_api_repository.py`
- `backend/app/repositories/online_queue_api_repository.py`
- `backend/app/repositories/qr_queue_api_repository.py`
- `backend/app/repositories/display_websocket_api_repository.py`

## `billing`
- Owned models:
- `backend/app/models/billing.py`
- `backend/app/models/payment.py`
- `backend/app/models/payment_webhook.py`
- `backend/app/models/payment_invoice.py`
- `backend/app/models/refund_deposit.py`
- `backend/app/models/dynamic_pricing.py`
- Owned services:
- `backend/app/services/billing_api_service.py`
- `backend/app/services/payments_api_service.py`
- `backend/app/services/payment_init_service.py`
- `backend/app/services/payment_webhooks_api_service.py`
- `backend/app/services/payment_reconciliation_api_service.py`
- Owned repositories:
- `backend/app/repositories/billing_api_repository.py`
- `backend/app/repositories/payments_api_repository.py`
- `backend/app/repositories/payment_init_repository.py`
- `backend/app/repositories/payment_webhooks_api_repository.py`
- `backend/app/repositories/payment_reconciliation_api_repository.py`

## `emr`
- Owned models:
- `backend/app/models/emr.py`
- `backend/app/models/emr_v2.py`
- `backend/app/models/emr_version.py`
- `backend/app/models/emr_template.py`
- `backend/app/models/visit.py`
- `backend/app/models/odontogram.py`
- `backend/app/models/dermatology_photos.py`
- `backend/app/models/ecg_data.py`
- Owned services:
- `backend/app/services/emr_v2_api_service.py`
- `backend/app/services/emr_templates_api_service.py`
- `backend/app/services/doctor_templates_api_service.py`
- `backend/app/services/dental_api_service.py`
- `backend/app/services/derma_api_service.py`
- `backend/app/services/cardio_api_service.py`
- Owned repositories:
- `backend/app/repositories/emr_v2_api_repository.py`
- `backend/app/repositories/emr_templates_api_repository.py`
- `backend/app/repositories/doctor_templates_api_repository.py`
- `backend/app/repositories/dental_api_repository.py`
- `backend/app/repositories/derma_api_repository.py`
- `backend/app/repositories/cardio_api_repository.py`

## `iam`
- Owned models:
- `backend/app/models/user.py`
- `backend/app/models/authentication.py`
- `backend/app/models/role_permission.py`
- `backend/app/models/two_factor_auth.py`
- Owned services:
- `backend/app/services/auth_api_service.py`
- `backend/app/services/authentication_api_service.py`
- `backend/app/services/roles_api_service.py`
- `backend/app/services/group_permissions_api_service.py`
- `backend/app/services/two_factor_auth_api_service.py`
- Owned repositories:
- `backend/app/repositories/auth_api_repository.py`
- `backend/app/repositories/authentication_api_repository.py`
- `backend/app/repositories/roles_api_repository.py`
- `backend/app/repositories/group_permissions_api_repository.py`
- `backend/app/repositories/two_factor_auth_api_repository.py`

## Allowed Inbound/Outbound Calls (Normative)

All cross-context calls must use explicit contracts/facades (Phase 4 target), not direct repository/model imports.

| Context | Allowed inbound callers | Allowed outbound calls |
|---|---|---|
| `patient` | `scheduling`, `queue`, `billing`, `emr`, `iam` | `iam` (permission checks only) |
| `scheduling` | `patient`, `queue`, `billing`, `iam` | `patient`, `queue`, `billing`, `iam` |
| `queue` | `patient`, `scheduling`, `billing`, `iam` | `patient`, `scheduling`, `billing`, `iam` |
| `billing` | `patient`, `scheduling`, `queue`, `emr`, `iam` | `patient`, `scheduling`, `queue`, `iam` |
| `emr` | `patient`, `scheduling`, `billing`, `iam` | `patient`, `scheduling`, `billing`, `iam` |
| `iam` | all contexts | none (policy source context; no business-context dependency) |

## Forbidden Direct Dependency Table

| Caller context | Forbidden direct dependency | Required integration path |
|---|---|---|
| Any context | Importing another context's `backend/app/repositories/*` module directly | Use target context facade/contract package |
| Any context | Importing another context's internal `backend/app/services/*_api_service.py` for business orchestration | Use public facade method only |
| `queue` | Direct use of billing repositories (`*payment*`, `billing_*`) | `billing` facade/contract (`payment status`, `charge`, `refund`) |
| `billing` | Direct use of queue repositories (`queue_*`, `online_queue_*`, `qr_queue_*`) | `queue` facade/contract (`queue state`, `token state`) |
| `scheduling` | Direct use of patient repositories for profile mutation | `patient` facade/contract (`lookup`, `validate`, `link`) |
| `emr` | Direct use of IAM repositories/services (`auth_*`, `roles_*`, `group_permissions_*`) | `iam` facade/contract (`access check`, `policy decision`) |
| `patient` | Direct import of billing or EMR internals for derived status | Read-only facade query contracts only |

## Transition Rules (While Refactor Is In Progress)

- Legacy direct imports are tolerated only if tracked as explicit migration items in `.ai-factory/PLAN.md`.
- New cross-context code must follow facade/contract path immediately.
- Boundary tests will be introduced to block new forbidden dependencies.

## Enforcement Plan

- Source of truth for architecture checks:
- `backend/app/domain/context_registry.py` (Task 2)
- `backend/tests/architecture/test_context_boundaries.py` (Task 4)
- CI enforcement:
- `.github/workflows/ci-cd-unified.yml` (Task 5)

## Notes

- This document maps boundaries; it does not replace detailed service-level API contracts.
- Runtime service files were not modified in Task 1, so no service startup logging changes were applied yet.
