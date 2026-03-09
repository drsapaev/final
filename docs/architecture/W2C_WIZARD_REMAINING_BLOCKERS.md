# Wave 2C Wizard Remaining Blockers

Date: 2026-03-09
Mode: readiness review, docs-only

## Remaining Coupling / Blocker Review

| Blocker | Severity | Blocks migration | Narrow fix possible | Notes |
|---|---|---:|---:|---|
| Hidden shared allocator logic | LOW | No | Yes | Resolved for mounted wizard-family; remaining shared logic is explicit kwargs assembly, not a hidden create call. |
| Billing coupling at allocation step | MEDIUM | No | Yes | Billing/invoice orchestration still shares the request transaction, but allocator call site is now isolated enough for a local boundary swap. |
| Source ownership ambiguity | LOW | No | Yes | Mounted same-day wizard path still uses explicit `source=\"desk\"`; no ambiguity found for this family. |
| Wizard-only claim ambiguity | LOW | No | Yes | Claim model is already clarified as queue-tag-level and runtime now follows it. |
| Visit linkage ambiguity | LOW | No | Yes | `visit_id` continues to flow through the handoff into queue-entry creation without a separate ambiguous branch. |

## Conclusion

No remaining blocker currently forces another decomposition slice before wizard
boundary migration.
