# Wave 2C Wizard Remaining Blockers

Date: 2026-05-06
Mode: docs-only replacement for stale PR #89
Depends on: merged replacement PR #267

## Remaining Coupling / Blocker Review

| Blocker | Severity | Blocks migration | Narrow fix possible | Notes |
|---|---|---:|---:|---|
| Hidden shared allocator logic | LOW | No | Yes | Resolved for mounted wizard-family: create branch is now an explicit handoff, not a hidden inline create call. |
| Billing coupling at allocation step | MEDIUM | No | Yes | Billing/invoice orchestration still shares the request transaction, but allocator materialization is isolated enough for a local boundary swap. |
| Source ownership ambiguity | LOW | No | Yes | Mounted same-day wizard path carries explicit `source` through the handoff payload. |
| Wizard-only claim ambiguity | LOW | No | Yes | Claim resolution stays in `MorningAssignmentService.prepare_wizard_queue_assignment(...)`. |
| Visit linkage ambiguity | LOW | No | Yes | `visit_id` remains part of the handoff kwargs passed to queue-entry creation. |

## Conclusion

No remaining blocker currently forces another decomposition slice before wizard boundary migration.
