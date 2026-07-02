# Wave 2C Queue Allocator Risk Matrix

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This matrix updates the earlier numbering risk review with the Phase 1.6
contract decisions.

## Risk Scale

- `Low`: well-defined contract, limited migration exposure
- `Medium`: clear contract, but meaningful runtime migration still required
- `High`: contract defined, but runtime drift remains large
- `Very High`: contract defined, but migration is entangled with legacy or
  multi-domain semantics

## Matrix

| Area | Current problem | Contract effect | Remaining migration risk | Recommendation |
|---|---|---|---|---|
| Allocator ownership | Multiple allocators with no single owner | Clear owner now defined: `QueueDomainService` | Medium | Safe to continue with contract-driven planning |
| Active-entry semantics | Different modules disagree on active states | Canonical active set now defined for domain contract | Medium to high | Migrate gradually; do not change all read models at once |
| Duplicate policy | Phone/telegram/patient rules conflict | Canonical identity-first duplicate contract now defined | High | Needs characterization tests before runtime adoption |
| Split allocation and create-row flows | Some callers ask for number, then create row later | Contract now forbids public split ownership | High | Confirmation and wizard paths need targeted migration |
| QR direct allocator | Router-level SQL allocator bypasses service owner | Contract clearly marks it as non-compliant | High | Defer until after owner boundary exists and tests are in place |
| Registrar legacy count-based allocator | Uses separate count-based model | Contract clearly marks it as non-canonical | High | Treat as legacy compatibility slice |
| Force-majeure transfer allocator | Separate exceptional allocator path | Contract allows special flow but not separate public owner | High | Migrate later under dedicated transfer semantics |
| Legacy `OnlineDay` counters | Second numbering worldview still exists | Contract isolates legacy outside the main owner | Very High | Keep out of first allocator execution phase |
| Fairness vs. ticket order | `queue_time` and `priority` can diverge from `number` order | Contract explicitly separates fairness from ticket numbering | Medium | Good for design clarity; still needs migration discipline |

## Main Outcome

Phase 1.6 reduces design ambiguity, but it does not reduce runtime migration
risk by itself.

The biggest improvement is conceptual:

- there is now a clear target owner
- there is now a clear active-entry contract
- there is now a clear duplicate-policy target
- there is now a clear numbering contract

The biggest remaining risk is still execution:

- replacing router-level and legacy allocators without changing behavior

## Readiness Signal

The project is now ready for a **targeted implementation plan** for allocator
introduction, but not yet for broad queue-mutation refactor.

Best next execution step after this phase:

- introduce characterization tests and a no-behavior-change `allocate_ticket()`
  compatibility boundary
