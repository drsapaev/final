# Wave 2C Force Majeure Decision Matrix

Date: 2026-03-09
Mode: contract-review

| Topic | Current runtime model | Target model | Conflict severity | What is needed first |
|---|---|---|---|---|
| Transfer allocation shape | New tomorrow row + old row cancelled | Same | Low | Nothing |
| Priority behavior | Explicit `priority=2` override | Same | Low | Nothing |
| `queue_time` behavior | New transfer-time timestamp | Same | Low | Nothing |
| Source semantics | `force_majeure_transfer` | Same | Low | Nothing |
| Visit linkage | Copy `visit_id` | Same | Low | Nothing |
| Duplicate behavior on target queue | Silent second active row possible | Explicit prevention / explicit conflict | High | Behavior correction if family is revisited |
| Numbering across cancelled history | Cancelled rows ignored in next-number calc | Monotonic target numbering | High | Behavior correction if family is revisited |
| Eligibility status set | Docs and code disagree | Explicit exceptional eligibility contract | Medium | Clarify docs/contract |

## Overall Decision

- current runtime model: exceptional transfer allocator with explicit policy overrides
- target model: exceptional-domain contract, not ordinary boundary caller
- next step: isolate from ordinary boundary-track and defer broad migration
