# W2D online_queue_legacy_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## In scope

- `backend/app/services/online_queue_legacy_api_service.py`
- cleanup status/architecture docs

## Why this file is a candidate

The file is a router-like compatibility artifact located under `services/`,
while the actual legacy online-queue endpoint module was already removed as a
dead/disabled surface.

Current repo evidence shows:

- no confirmed in-repo source import of `online_queue_legacy_api_service`
- no route registration through this file
- no direct backend test dependency

## Why this is the narrowest safe cleanup

This is duplicate/unmounted residue removal, not a QR or queue-domain refactor.

The slice intentionally does not:

- change mounted QR/queue routes
- change `QRQueueService`
- change queue behavior

## Validation plan

- OpenAPI contract check
- full backend suite to catch any hidden bootstrap/import dependency
