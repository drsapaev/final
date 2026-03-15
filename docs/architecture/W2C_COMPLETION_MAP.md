# Wave 2C Completion Map

Date: 2026-03-09
Mode: analysis-first, docs-first

## Summary

Wave 2C produced a complete main production queue allocator track around
`QueueDomainService.allocate_ticket()`, plus explicit isolation for non-main
track domains.

## Completion map

| Area | Status | Key docs | Key code artifacts | Final verdict |
|---|---|---|---|---|
| Core queue contracts | Complete | `docs/architecture/W2C_QUEUE_DISCOVERY.md`, `docs/architecture/W2C_QUEUE_STATE_MACHINE.md`, `docs/architecture/W2C_QUEUE_INVARIANTS.md`, `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`, `docs/architecture/W2C_QUEUE_NUMBERING_CONTRACT.md`, `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`, `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md` | `backend/app/services/queue_domain_service.py`, `backend/app/services/queue_status.py`, `backend/app/repositories/queue_read_repository.py` | Main queue contract foundation established |
| Allocator boundary preparation | Complete | `docs/architecture/W2C_ALLOCATOR_OWNERSHIP.md`, `docs/architecture/W2C_ALLOCATOR_COMPATIBILITY_LAYER.md`, `docs/architecture/W2C_ALLOCATOR_MIGRATION_STRATEGY.md` | `backend/app/services/queue_domain_service.py`, `backend/app/services/context_facades/queue_facade.py`, `backend/app/domain/contracts/queue_contracts.py` | Compatibility boundary exists and is proven in production slices |
| Confirmation family | Complete | `docs/architecture/W2C_CONFIRMATION_BEHAVIOR_CORRECTION.md`, `docs/architecture/W2C_CONFIRMATION_BOUNDARY_MIGRATION.md`, `docs/status/W2C_CONFIRMATION_BOUNDARY_MIGRATION_STATUS.md` | `backend/app/services/visit_confirmation_service.py`, `backend/app/repositories/visit_confirmation_repository.py` | Mounted confirmation flow is corrected and boundary-aligned |
| Registrar batch-only family | Complete | `docs/architecture/W2C_REGISTRAR_BATCH_BEHAVIOR_CORRECTION.md`, `docs/architecture/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION.md`, `docs/status/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION_STATUS.md` | `backend/app/api/v1/endpoints/registrar_integration.py` | Mounted registrar batch-only create path is boundary-aligned |
| Registrar wizard family | Complete | `docs/architecture/W2C_REGISTRAR_WIZARD_BEHAVIOR_CORRECTION.md`, `docs/architecture/W2C_WIZARD_ALLOCATOR_EXTRACTION.md`, `docs/architecture/W2C_WIZARD_CREATE_BRANCH_EXTRACTION.md`, `docs/architecture/W2C_WIZARD_BOUNDARY_MIGRATION.md`, `docs/status/W2C_WIZARD_BOUNDARY_MIGRATION_STATUS.md` | `backend/app/services/registrar_wizard_queue_assignment_service.py`, `backend/app/services/morning_assignment.py` | Mounted wizard same-day queue path is corrected, decomposed, and boundary-aligned |
| QR full-update family | Complete | `docs/architecture/W2C_QR_CREATE_BRANCH_EXTRACTION.md`, `docs/architecture/W2C_QR_PAYLOAD_COMPATIBILITY_FIX.md`, `docs/architecture/W2C_QR_BOUNDARY_MIGRATION.md`, `docs/status/W2C_QR_BOUNDARY_MIGRATION_STATUS.md` | `backend/app/services/qr_full_update_queue_assignment_service.py`, `backend/app/services/queue_service.py` | Mounted QR full-update create branch is boundary-aligned |
| OnlineDay legacy isolation | Complete as side-track isolation | `docs/architecture/W2C_ONLINEDAY_ISLAND_BOUNDARY.md`, `docs/architecture/W2C_ONLINEDAY_CLEANUP_TRACK.md`, `docs/status/W2C_ONLINEDAY_TRACK_DECISION.md`, `docs/status/W2C_ONLINEDAY_MAIN_TRACK_SEPARATION.md` | `backend/app/models/online.py`, `backend/app/services/online_queue.py`, `backend/app/api/v1/endpoints/appointments.py`, `backend/app/api/v1/endpoints/queues.py`, `backend/app/api/v1/endpoints/board.py` | OnlineDay removed from main track and isolated as separate legacy island |
| Force majeure isolation | Complete as side-track isolation | `docs/architecture/W2C_FORCE_MAJEURE_CONTRACT.md`, `docs/architecture/W2C_FORCE_MAJEURE_ISLAND_BOUNDARY.md`, `docs/architecture/W2C_FORCE_MAJEURE_LOCAL_CONTRACT_OWNERSHIP.md`, `docs/status/W2C_FORCE_MAJEURE_DOMAIN_DECISION.md`, `docs/status/W2C_FORCE_MAJEURE_MAIN_TRACK_SEPARATION.md` | `backend/app/api/v1/endpoints/force_majeure.py`, `backend/app/services/force_majeure_service.py`, `backend/app/services/force_majeure_api_service.py` | Force majeure removed from ordinary allocator track and isolated as exceptional-domain |
| Deferred cleanup | Deferred intentionally | `docs/status/W2C_PHASE21_DEFERRED_CALLERS.md`, `docs/status/W2C_QUEUE_TRACK_STATUS_AFTER_FORCE_MAJEURE.md` | duplicate/unmounted mirrors and stale helpers across legacy queue modules | Not part of Wave 2C completion criteria |

## Completion-map verdict

Wave 2C is complete as a queue allocator architecture track:

- the main production allocator path is aligned
- side tracks are explicitly isolated
- remaining work is follow-up work, not a blocker for the Wave 2C objective
