# Wave 2C High-Risk Migration Readiness

Date: 2026-03-07
Mode: analysis-first, docs-only

| Family | Readiness | Why not ready now | What would move it forward |
|---|---|---|---|
| Registrar batch and wizard flows | `READY_AFTER_CONTRACT_CLARIFICATION` | Family currently mixes queue-service-backed batch writes with wizard split allocation and legacy count-based same-day creation | Split family into subfamilies first, then characterize wizard behavior separately from modern batch behavior |
| Confirmation split-flow | `READY_AFTER_CHARACTERIZATION_TESTS` | Uses queue-service helpers, but still splits allocation from row creation inside visit confirmation | Add family-specific characterization for same-day replay, multi-queue confirmation, and doctor or user specialist fallback |
| `qr_queue.py` direct SQL allocator branches | `BLOCKED_BY_TRANSACTION_MODEL` | Direct SQL numbering is interleaved with patient creation, visit updates, invoice-sensitive logic, and multi-entry branching | First isolate mutation subflows and document transaction phases before any boundary migration |
| Force majeure allocator paths | `BLOCKED_BY_TRANSACTION_MODEL` | Transfer flow reallocates numbers while cancelling old entries and sending notifications after commit | Characterize concurrent transfer and duplicate-tomorrow behavior, then define explicit transfer transaction contract |
| `OnlineDay` and other legacy allocator paths | `BLOCKED_BY_LEGACY` | Legacy counter model is independent from SSOT queue allocation and uses different duplicate and fairness assumptions | Decide whether to retire, freeze behind adapter, or migrate in a separate legacy track |
| Unmounted or duplicate queue entry services | `READY_AFTER_CONTRACT_CLARIFICATION` | Runtime ownership is unclear; some helpers are likely stale or shadow modules | Confirm mounted runtime owner first, then either delete, freeze, or align duplicate service modules |

## Readiness Verdict

Closest family to migration:

- confirmation split-flow

Closest subfamily after that:

- registrar batch path only, not the combined registrar family

Still blocked:

- `qr_queue.py` direct SQL branches
- force majeure transfer allocator
- `OnlineDay` legacy family
