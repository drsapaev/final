# Wave 2C Queue Numbering Risk Matrix

Date: 2026-03-07
Mode: analysis-first, docs-only

## Risk Scale

- `Low`: one clear owner, low race risk, low migration cost
- `Medium`: usable today, but policy or race assumptions are implicit
- `High`: multiple hidden assumptions, race risk, or policy drift
- `Very High`: multiple conflicting models or legacy ambiguity

## Risk Matrix

| Mechanism | Current owner | Race condition risk | Duplicate risk | Fairness violation risk | Migration difficulty | Overall risk |
|---|---|---|---|---|---|---|
| `queue_service.get_next_queue_number()` + `create_queue_entry()` | `backend/app/services/queue_service.py` | Medium: `max(number)+1` without explicit lock | Medium: depends on caller duplicate policy | Medium: number is not the full fairness model | Medium | Medium |
| `join_queue_with_token()` allocator path | `queue_service.py` | Medium | Medium | Medium | Medium | Medium |
| `qr_queue.py` direct SQL `MAX(number)+1` | `backend/app/api/v1/endpoints/qr_queue.py` | High | High: bypasses some centralized checks | High: used inside edit/add-service flow with fairness-sensitive timestamps | High | High |
| Registrar legacy `start_number + current_count` | `backend/app/api/v1/endpoints/registrar_integration.py` | Medium to high | Medium | Medium | High | High |
| Confirmation flow: ask number, then create entry | `visit_confirmation_service.py` | Medium | Medium | Medium | Medium | Medium |
| Registrar wizard confirmation path | `registrar_wizard_api_service.py` | Medium | Medium | Medium | High: direct model create | High |
| Force majeure `_get_next_queue_number()` | `force_majeure_service.py` | Medium | Low to medium | High: transfer priority intentionally overrides ordinary ordering | High | High |
| Legacy `OnlineDay` `last_ticket` counter | `online_queue.py` / `appointments.py` | Medium | Medium | Medium | Very High: different model, different operator semantics | Very High |
| Stale `crud/queue.py` ticket path | `crud/queue.py` | Unknown to high | Unknown | Unknown | Very High | Very High |

## Key Findings

1. There is no low-risk numbering mechanism that is already used everywhere.
2. The riskiest area is not the main allocator itself; it is the coexistence of
   multiple allocators with different surrounding policies.
3. Fairness risk is high whenever a flow combines:
   - manual or direct number assignment
   - queue-time-sensitive editing
   - priority overrides
4. Legacy paths increase migration difficulty even when they do not directly
   write SSOT queue-entry numbers.

## Safe vs. Unsafe Work Classification

### Safe in analysis only

- document runtime numbering sources
- map allocator ownership
- add tests that assert current behavior without changing policy

### Not safe without domain agreement

- replacing direct SQL allocator paths with a shared helper
- extracting a single repository method and assuming behavior is preserved
- collapsing duplicate checks into one rule without source-by-source agreement
- changing number allocation around restore, reorder, or transfer flows

## Risk Verdict

`W2C-MS-005` is above the current safe threshold for Wave 2C Phase 1.

It is not blocked only by implementation difficulty. It is blocked by missing
policy decisions around:

- allocator ownership
- duplicate policy ownership
- fairness semantics vs. ticket-order semantics
- legacy compatibility scope
