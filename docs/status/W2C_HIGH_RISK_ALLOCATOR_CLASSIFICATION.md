# Wave 2C High-Risk Allocator Classification

Date: 2026-03-07
Mode: analysis-first, docs-only

| Family | Risk level | Risk type | Why |
|---|---|---|---|
| Registrar batch and wizard flows | High | `TRANSACTION_CRITICAL`, `DUPLICATE_POLICY_CRITICAL`, `AMBIGUOUS_RUNTIME`, `LEGACY_COUPLED` | Family mixes modern queue-service-backed writes with wizard split flows and a legacy same-day count-based allocator |
| Confirmation split-flow | High | `TRANSACTION_CRITICAL`, `DUPLICATE_POLICY_CRITICAL`, `FAIRNESS_CRITICAL`, `AMBIGUOUS_RUNTIME` | Number allocation and queue-row creation are still split, but happen inside visit confirmation and same-day status changes |
| `qr_queue.py` direct SQL allocator branches | Critical | `DIRECT_SQL`, `TRANSACTION_CRITICAL`, `DUPLICATE_POLICY_CRITICAL`, `FAIRNESS_CRITICAL`, `SIDE_EFFECT_HEAVY`, `AMBIGUOUS_RUNTIME` | Direct `MAX(number)+1` allocation sits inside a mutation-heavy handler that also touches visits, services, sessions, and invoice-sensitive paths |
| Force majeure allocator paths | High | `TRANSACTION_CRITICAL`, `FAIRNESS_CRITICAL`, `SIDE_EFFECT_HEAVY`, `AMBIGUOUS_RUNTIME` | Transfer flow reallocates numbers, changes priority and `queue_time`, cancels old entries, and sends notifications |
| `OnlineDay` and other legacy allocator paths | Critical | `LEGACY_COUPLED`, `FAIRNESS_CRITICAL`, `DUPLICATE_POLICY_CRITICAL`, `AMBIGUOUS_RUNTIME` | Uses a separate counter model and separate duplicate memory, so parity with SSOT queues is not automatic |
| Unmounted or duplicate queue entry services | Medium | `AMBIGUOUS_RUNTIME`, `LEGACY_COUPLED` | Risk is mostly ownership confusion and stale helper drift rather than immediate runtime mutation complexity |

## Classification Notes

- `Critical` means boundary migration should not start before family-specific
  prerequisites are complete.
- `High` means migration is possible later, but only after narrowing the family
  and locking down current behavior with targeted characterization.
- `Medium` means the code may be easier to clean up later, but it should not be
  touched until runtime ownership is explicit.
