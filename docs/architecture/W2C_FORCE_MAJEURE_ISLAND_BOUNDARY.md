# Wave 2C Force Majeure Island Boundary

Date: 2026-03-09
Mode: analysis-first, isolation-first

## Boundary statement

The `force_majeure` family is a separate exceptional-domain island.

It must not be treated as part of the ordinary SSOT queue allocator track built
around:

- `DailyQueue`
- `OnlineQueueEntry`
- `QueueDomainService.allocate_ticket()`

## What belongs to the force_majeure island

### Mounted exceptional endpoints

- `backend/app/api/v1/endpoints/force_majeure.py`
  - `transfer_queue_to_tomorrow()`
  - `cancel_queue_with_refund()`
  - `get_pending_entries_for_force_majeure()`
  - refund-request management endpoints
  - deposit endpoints

### Domain service ownership

- `backend/app/services/force_majeure_service.py`
  - `get_pending_entries()`
  - `transfer_entries_to_tomorrow()`
  - `cancel_entries_with_refund()`
  - `_get_next_queue_number()`
  - refund / deposit helpers

### API orchestration layer

- `backend/app/services/force_majeure_api_service.py`
- `backend/app/repositories/force_majeure_api_repository.py`

## Transfer-domain ownership

This island owns an operational domain that combines:

- queue transfer to tomorrow
- queue cancellation
- refund/deposit side effects
- patient notifications

That combination is exactly why it does not fit the ordinary allocator track.

## Local rules that intentionally override normal queue contracts

- new target-queue number on transfer
- new transfer-time `queue_time`
- explicit priority override
- exceptional source `force_majeure_transfer`
- preservation of `visit_id` across transfer

## What must not be confused with the SSOT allocator track

Do not treat force majeure as if it were:

- just another queue join/create caller
- a normal duplicate-policy path
- ordinary fairness based on untouched `queue_time`
- a routine `QueueDomainService.allocate_ticket()` migration candidate

## Boundary verdict

The force_majeure island is:

- live
- mounted
- operationally important
- intentionally exceptional

It should stay outside the main queue allocator track unless a later explicit
business/domain decision redefines its overrides.
