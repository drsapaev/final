# Wave 2A Human Review Classification

Date: 2026-03-06  
Mode: analysis-first

## Classification Rules

- `SAFE_REFACTOR`: read-only or narrowly scoped router logic; no queue/payment/lifecycle mutation.
- `QUEUE_COUPLED`: handler mutates queue state, queue settings, or queue-derived routing semantics.
- `PAYMENT_COUPLED`: handler creates or reconciles payments, invoices, providers, or revenue state.
- `TRANSACTION_CRITICAL`: handler coordinates multiple writes or relies on commit/rollback ordering.
- `MIXED_LOGIC`: handler mixes read-model shaping, orchestration, and persistence policy in one router block.

## Slice Classification

| Slice / Area | Classification | Why |
|---|---|---|
| `W2A-SR-011` (`services.py` queue-adjacent handlers) | `MIXED_LOGIC`, `QUEUE_COUPLED` | Handlers are read-only, but they define queue taxonomy and registrar/frontend grouping semantics. Existing service methods exist, yet the business meaning of these mappings is queue-domain policy, not generic catalog CRUD. |
| `W2A-SR-040` (`visits.py` status/reschedule handlers) | `QUEUE_COUPLED`, `TRANSACTION_CRITICAL`, `MIXED_LOGIC` | Router mutates visit status/date and linked queue-entry status in the same request. Transaction ordering matters because visit lifecycle and queue lifecycle must stay coherent. |
| `W2A-SR-020` (`admin_departments.py`) | `QUEUE_COUPLED`, `TRANSACTION_CRITICAL`, `MIXED_LOGIC` | Department bootstrap and queue settings creation are interleaved with registration settings and optional service provisioning. |
| `W2A-SR-030` (`doctor_integration.py`) | `QUEUE_COUPLED`, `TRANSACTION_CRITICAL`, `PAYMENT_COUPLED` | Doctor flow completes visits, may create payments through billing, and derives visit state from queue state. |
| `W2A-SR-050` (`registrar_integration.py`) | `QUEUE_COUPLED`, `TRANSACTION_CRITICAL`, `MIXED_LOGIC` | Registrar endpoints combine queue read models, queue start transitions, and batch queue creation logic. |
| `W2A-SR-060` (`registrar_wizard.py`) | `QUEUE_COUPLED`, `PAYMENT_COUPLED`, `TRANSACTION_CRITICAL`, `MIXED_LOGIC` | Cart/invoice/payment flow is the strongest crossover slice: visits, queue entries, invoices, price overrides, provider callbacks. |
| `W2A-SR-070` (`qr_queue.py`) | `QUEUE_COUPLED`, `TRANSACTION_CRITICAL` | High-density queue lifecycle mutations plus notifications and display side effects. |
| `W2A-SR-080` (`cashier.py`) | `PAYMENT_COUPLED`, `TRANSACTION_CRITICAL` | Cashier endpoints create/confirm/refund payments and reconcile visit state. |
| `W2A-SR-090` (`appointments.py`) | `MIXED_LOGIC`, `PAYMENT_COUPLED` | File mixes read-only appointment listing, pending-payment aggregation, and queue open/close administration. |
| `W2A-SR-100` (`admin_stats.py`) | `PAYMENT_COUPLED`, `SAFE_REFACTOR` | Handlers are read-only analytics, but the domain is payment-heavy reporting. Safe extraction is possible, yet it belongs to a reporting/payment track more than to core Wave 2A cleanup. |

## Human Review Outcome

- Continue automatic Wave 2A refactor only for clearly bounded micro-slices with no domain-state mutation.
- Treat queue lifecycle, visit lifecycle, registrar orchestration, and payment reconciliation as separate architecture tracks.
- Do not auto-refactor `W2A-SR-040`, `W2A-SR-060`, `W2A-SR-070`, or `W2A-SR-080`.
