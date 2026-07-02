# Wave 2C Registrar Wizard Classification

Date: 2026-03-08
Mode: characterization-only

| Subflow | Current runtime owner | Classification | Why |
|---|---|---|---|
| `RW-SF-01` same-day cart create with immediate queue assignment | `registrar_wizard.py` + `MorningAssignmentService` | `BLOCKED_BY_BILLING_COUPLING` | visit creation, invoice creation, and queue allocation happen in one mounted request |
| `RW-SF-02` same-day cart create with existing queue claim reuse | `registrar_wizard.py` + `MorningAssignmentService` | `BLOCKED_BY_CLAIM_AMBIGUITY` | reuse is queue-local and not aligned to the canonical active-entry contract |
| `RW-SF-03` same specialist with different `queue_tag` values | `registrar_wizard.py` + `MorningAssignmentService` | `BLOCKED_BY_CLAIM_AMBIGUITY` | one visit can expand into multiple queue claims, so specialist-level ownership is not yet the correct migration assumption |
| `RW-SF-04` multi-visit cart for different specialists | `registrar_wizard.py` + `MorningAssignmentService` | `BLOCKED_BY_BILLING_COUPLING` | queue allocation still runs inside shared invoice/cart orchestration |
| `RW-SF-05` future-day cart create | `registrar_wizard.py` | `READY_FOR_CHARACTERIZED_CORRECTION` | no immediate allocator action, but still part of the same mixed runtime family |
| `RW-SF-06` registrar confirmation bridge | `visit_confirmation_service.py` | `READY_FOR_BOUNDARY_MIGRATION` | already clarified and migrated in its own family track; not part of this pass |
| dead helper `_create_queue_entries()` | `registrar_wizard.py` | `LEGACY_LATE_TRACK` | no confirmed mounted caller in current runtime |
| duplicate `registrar_wizard_api_service.py` module | unmounted duplicate | `LEGACY_LATE_TRACK` | mirrors runtime but is not mounted in `backend/app/api/v1/api.py` |

## Classification Verdict

The broader registrar wizard family is not ready for direct boundary migration.

The dominant blockers are:

- billing coupling inside the mounted `/registrar/cart` request
- unresolved claim semantics caused by queue-tag expansion
