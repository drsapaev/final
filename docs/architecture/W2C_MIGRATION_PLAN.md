# Wave 2C Migration Plan

Date: 2026-03-06
Mode: analysis-first

## Goal

Migrate queue lifecycle code toward a clear domain boundary without changing production behavior during the early phases.

## Principles

- keep behavior stable
- move one responsibility at a time
- do not mix queue refactor with payment hardening
- do not migrate legacy `OnlineDay` blindly
- add tests before moving mutation paths

## Phase 0: Baseline Freeze

Purpose:

- freeze the actual queue status vocabulary
- document active-status subsets
- document legacy vs SSOT queue split

Outputs:

- `W2C_QUEUE_DISCOVERY.md`
- `W2C_QUEUE_STATE_MACHINE.md`
- `W2C_QUEUE_INVARIANTS.md`

Go gate:

- state machine agreed
- invariants agreed
- no unresolved uncertainty about active-status policy

## Phase 1: Introduce QueueDomainService

Purpose:

- add a queue domain boundary without moving routers yet

Scope:

- create `QueueDomainService`
- create or normalize `QueueRepository` and `VisitRepository`
- keep existing endpoints and public contracts unchanged

Constraints:

- no queue semantics change
- no legacy queue migration
- no payment-coupled behavior change

Go gate:

- service methods exist
- targeted unit tests prove status normalization and numbering behavior

Status:

- partially completed on 2026-03-07
- done:
  - `QueueDomainService` skeleton added
  - status normalization helper added
  - first read-only slices completed
- still deferred:
  - numbering extraction
  - duplicate-policy extraction
  - any mutation-family migration

## Phase 2: Move Read-Only Queue Endpoints

Purpose:

- migrate safe read paths first

Scope:

- queue position reads
- queue cabinet reads
- queue limits/status reads
- queue snapshot/status reads

Constraints:

- no mutation handlers
- no payment or visit lifecycle behavior

Go gate:

- read-only endpoints use service/repository boundaries
- queue tests and full backend tests stay green

Status:

- started in Phase 1 with `W2C-MS-001` and `W2C-MS-006`
- remaining safe read-only slices are `W2C-MS-003`, `W2C-MS-002`, and possibly `W2C-MS-005`

## Phase 3: Move State Transitions

Purpose:

- move queue lifecycle mutations behind `QueueDomainService`

Scope order:

1. `call_next`
2. `no_show` and `restore_as_next`
3. diagnostics and incomplete
4. reorder writes
5. visit-linked cancel/reschedule

Constraints:

- one mutation family per slice
- explicit transition tests required for each moved family
- post-commit side effects must be preserved

Stop gate:

- if alias mapping is still unclear
- if transaction boundary becomes less clear than current code

## Phase 4: Remove Router-Level Queue DB Access

Purpose:

- eliminate direct ORM mutation in queue lifecycle routers

Scope:

- queue runtime routers
- registrar queue mutation routers
- visit-linked queue mutations where still applicable

Constraints:

- do not include payment/provider flows here
- leave payment-coupled completion behavior behind an explicit integration boundary

Success signal:

- routers only validate request and call service
- queue rules live in domain service
- repository layer owns persistence

## Phase 5: Legacy Queue Retirement Plan

Purpose:

- address `OnlineDay` and `appointments` queue admin after the SSOT queue lifecycle is stable

Scope:

- map legacy `waiting/serving/done` counters to SSOT queue model
- migrate open/close-day semantics deliberately

Dependencies:

- must happen after queue state machine and active-status policy are stable

Note:

This phase is not part of the first Wave 2C execution slices.

## Coordination with Other Wave 2 Tracks

- `Wave 2B`:
  - contract-hardening can help with read-model endpoints
- `Wave 2D`:
  - payment/provider reconciliation must stay separate

Queue completion flows that create or infer payment state should stop at a queue-domain boundary and hand off to Wave 2D logic explicitly.

## Recommended First Execution Order

1. implement `QueueDomainService` facade only
2. take one safe read-only slice
3. add transition tests
4. migrate one runtime mutation family
5. defer payment-coupled completion flows until queue and payment ownership is clear
