# W2D API Reference Queue Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document the whole queue subsystem. The goal was
to correct high-confidence drift in the `Queue` section after the Wave 2C queue
architecture work and later protected cleanup/parity slices.

## Findings

### Queue section was still documenting pre-split routes

- the doc still advertised:
  - `GET /queue/`
  - `POST /queue/join`
  - `POST /queue/{id}/call`
  - `POST /queue/{id}/complete`
- the live queue contract is now split across:
  - modern `/api/v1/queue/*` surfaces in `qr_queue.py`,
    `queue_position.py`, and `queue_reorder.py`
  - legacy compatibility routes under `/api/v1/queue/legacy/*`

### Join flow has moved to a session-based public contract

- current recommended public join flow is:
  - `POST /api/v1/queue/join/start`
  - `POST /api/v1/queue/join/complete`
- `POST /api/v1/queue/legacy/join` still exists, but the mounted owner marks it
  as deprecated compatibility behavior

### Current queue operations are broader than the old summary implied

- public queue reads now include:
  - `GET /api/v1/queue/available-specialists`
  - `GET /api/v1/queue/position/{entry_id}`
  - `GET /api/v1/queue/position/by-number/{queue_number}`
- staff queue runtime now includes:
  - `GET /api/v1/queue/status/{specialist_id}`
  - `POST /api/v1/queue/{specialist_id}/call-next`
- additional active queue surfaces also live under:
  - `/api/v1/queue/admin/*`
  - `/api/v1/queue/entry/*`
  - `/api/v1/queue/reorder/*`
  - `/api/v1/queue/position/notify/*`

### Not every live response shape is safely documentable from generated schema

- `POST /api/v1/queue/join/complete` currently has an untyped `200` response in
  generated `backend/openapi.json`
- for that operation, the honest docs move was to document the request shape
  and downgrade the response to an implementation-backed note instead of
  inventing a stable schema

## What changed

- updated the `Queue` section in `docs/API_REFERENCE.md` to a curated modern
  queue map
- replaced the stale `/queue/join` and `/queue/{id}/call` narrative with the
  live session-based join and position/status surfaces
- explicitly marked `/queue/legacy/*` as compatibility routes, not the primary
  contract for new integrations
- kept untyped `join/complete` response language intentionally conservative

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/queue.py`
- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/api/v1/endpoints/queue_position.py`
- `backend/app/api/v1/endpoints/queue_reorder.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Best next candidate:

- `Payments`
