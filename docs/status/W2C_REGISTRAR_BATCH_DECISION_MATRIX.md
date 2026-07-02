# Wave 2C Registrar Batch Decision Matrix

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78

| Decision | Current answer | Review consequence |
| --- | --- | --- |
| Claim owner | Doctor profile id (`doctors.id`) | Reject docs/code that use `specialist_user_id` as the current contract. |
| Request field | `specialist_id` | Treat it as doctor-profile input, not user-account input. |
| Queue bucket | First service `queue_tag` | Do not document `queue_tag=None` as current mounted behavior. |
| Same-doctor multi-service batch | One queue row in first service bucket | Per-service rows need a separate runtime/product decision. |
| Duplicate key | patient + doctor + day + bucket | Future tests should name all four dimensions. |
| Active statuses | Must be made explicit per runtime PR | Do not claim broader enforcement without tests. |

## Merge Decision Guidance

A docs-only PR is useful when it reduces ambiguity without changing runtime. A runtime PR is not safe to merge unless its tests prove the selected row-cardinality and duplicate behavior.
