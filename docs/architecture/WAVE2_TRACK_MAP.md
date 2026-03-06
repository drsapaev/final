# Wave 2 Track Map

Date: 2026-03-06  
Source: Wave 2A human review pass

## Wave 2A: Service/Repository Completion

- Goal:
  - finish safe router -> service -> repository conversions where domain semantics are already stable
- Typical scope:
  - read-only metadata endpoints
  - simple CRUD or read-model handlers without queue/payment lifecycle mutations
- Current state:
  - almost exhausted after `W2A-SR-001`, `002`, `003`, `010`, `012`, `013`
- Entry rule:
  - no queue-state mutation
  - no payment reconciliation
  - no cross-module transaction redesign

## Wave 2B: API Contract Hardening

- Goal:
  - stabilize OpenAPI, response shapes, frontend/backend alignment, and contract tests
- Typical scope:
  - schema normalization
  - response consistency
  - frontend/backend parity gates
  - read-only listing/reporting endpoints that mainly need contract discipline
- Candidate overlap:
  - `appointments.py:list_appointments`
  - read-only admin/reporting endpoints

## Wave 2C: Queue Lifecycle Refactor

- Goal:
  - isolate queue lifecycle rules, queue state transitions, and registrar/doctor queue orchestration
- Typical scope:
  - `W2A-SR-011` if queue metadata is treated as queue policy
  - `W2A-SR-040`
  - `W2A-SR-020`
  - `W2A-SR-030`
  - `W2A-SR-050`
  - `W2A-SR-070`
- Required guardrails:
  - human review
  - explicit state-transition matrix
  - regression tests around queue statuses, display notifications, and registrar dashboards

## Wave 2D: Payment Flow Hardening

- Goal:
  - isolate invoice/provider/payment reconciliation and payment-heavy reporting
- Typical scope:
  - `W2A-SR-060`
  - `W2A-SR-080`
  - payment-heavy parts of `W2A-SR-090`
  - payment analytics in `W2A-SR-100`
- Required guardrails:
  - human review
  - provider integration test plan
  - explicit accepted-risk decisions for billing/payment status coupling

## Recommended Sequencing

1. Finish Human Review Pass.
2. If a micro-slice is read-only and stable, execute it under Wave 2A or Wave 2B.
3. Move queue-lifecycle work to Wave 2C.
4. Move payment/provider work to Wave 2D.

## Stop / Go Guidance

- Continue Wave 2A only if the slice is read-only or metadata-only.
- Switch to Wave 2C when queue state, visit lifecycle, or registrar queue flows are involved.
- Switch to Wave 2D when invoice/provider/payment state is involved.
