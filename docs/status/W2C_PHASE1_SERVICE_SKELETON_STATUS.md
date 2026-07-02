# Wave 2C Phase 1 Service Skeleton Status

Date: 2026-03-07
Status: done

## Files Added / Changed

- `backend/app/services/queue_domain_service.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_status.py`
- `backend/app/services/queue_reorder_api_service.py`
- `backend/app/repositories/queue_reorder_api_repository.py`
- `backend/app/repositories/queue_position_api_repository.py`

## Boundaries Introduced

- `QueueDomainService` is now the explicit read-only queue domain boundary for
  queue snapshot/status reads.
- `QueueReadRepository` is now the read-only persistence boundary used by
  `QueueDomainService`.
- `queue_status` centralizes canonical alias mapping and raw-status groups for
  Phase 1 read paths.

## What Remains Legacy

- queue mutation orchestration in `qr_queue.py`
- registrar queue mutation flows
- doctor queue mutation flows
- visit-linked queue mutation flows
- numbering and duplicate-policy logic in `queue_service.py`
- legacy `OnlineDay` queue administration

## Behavior-Safety Notes

- no persisted status values were rewritten
- no public endpoint payloads were changed
- reorder write handlers still use their existing repository and semantics
- only read-only queue snapshot/status methods were re-routed through the new boundary
